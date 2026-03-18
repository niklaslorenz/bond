import logging

from returns.result import Success

from bond.conversation import Conversation
from bond.endpoints.chat_completions import (AssistantMessage,
                                             ChatCompletionsProvider,
                                             ChatCompletionsWrapper,
                                             FunctionCall, TextChunk)
from bond.tools.tool import Toolbox

logger = logging.getLogger(__name__)


def _do_tool_call(toolbox: Toolbox, function_call: FunctionCall) -> str:
    result = toolbox.call_tool(function_call.name, function_call.arguments)
    logger.info(f"Tool call returned object of type {type(result)}:\n{result}")
    if isinstance(result, Success):
        return result.unwrap()
    else:
        return f"An error occured before the tool execution: {result.failure()}"


class SingleTurn:
    def __init__(
        self,
        provider: ChatCompletionsProvider,
        model: str,
        toolbox: Toolbox,
        system_message: str | None = None,
        **additional_model_arguments,
    ):
        self.toolbox = toolbox
        self.system_message = system_message
        self.chat_completions = ChatCompletionsWrapper(provider)
        self.model = model
        self.additional_model_arguments = additional_model_arguments

    def run(self, user_message: str) -> str:
        conversation = Conversation.create(self.system_message)
        conversation.add_user_message(user_message)

        response_acc: list[str] = []
        while True:
            response = self.chat_completions.chat_completion(
                self.model,
                conversation.get_messages(),
                tools=self.toolbox.get_tool_descriptions(),
                **self.additional_model_arguments,
            )
            message = response.choices[0].message

            # Add text content to the output
            if message.content is not None:
                for chunk in message.content:
                    if isinstance(chunk, TextChunk):
                        response_acc.append(chunk.text)

            # Return when no tools are called
            if message.tool_calls is None:
                return "\n".join(response_acc).strip("\n ")

            # Handle Tool calls
            conversation.add_message(
                AssistantMessage(content=message.content, tool_calls=message.tool_calls)
            )
            for tool_call in message.tool_calls:
                result = _do_tool_call(self.toolbox, tool_call.function)
                conversation.add_tool_str_response(tool_call, result)
