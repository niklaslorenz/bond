import logging

from returns.result import Failure, Result, Success

from bond.conversation.conversation import Conversation
from bond.conversation.types import Message, SystemMessage, TextChunk, UserMessage
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.providers.general.summarization import SummaryHandlerOptions
from bond.providers.general.util.markdown_renderer import MarkdownRenderer

logger = logging.getLogger(__name__)


class BulkMarkdownSummarizationStrategy:
    def __init__(self):
        pass

    def __call__(
        self,
        conversation: Conversation,
        turns: int | None,
        chat_completions: ChatCompletionsEndpoint,
        options: SummaryHandlerOptions,
    ) -> Result[str, str]:
        renderer = MarkdownRenderer(condensed=True)
        rendered = renderer.render_conversation(conversation, turns)
        system_message = SystemMessage(content=[TextChunk(text=options.prompt)])
        message_list: list[Message] = [UserMessage(content=[TextChunk(text=rendered)])]

        response = chat_completions.chat_completion(
            options.prompt, message_list, [], system_message, options.model_options
        )
        if response.choices[0].message.tool_calls is not None:
            logger.warning(
                "Episode summarization call generated tool calls which is unexpected.\n"
                + "\n".join(
                    f"Function: {tool_call.function.name}\nParameters: {tool_call.function.arguments}"
                    for tool_call in response.choices[0].message.tool_calls
                )
            )
        if (content := response.choices[0].message.content) is None:
            return Failure("Model returned with no content")
        summary = "".join(
            [chunk.text for chunk in content if isinstance(chunk, TextChunk)]
        )
        if summary == "":
            return Failure("Model returned with no content")
        return Success(summary)
