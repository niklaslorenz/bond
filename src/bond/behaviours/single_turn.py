import logging

from returns.result import Success

from bond.behaviours.behaviour_event import (AppendMessageChunkEvent,
                                             CallToolEvent, FullResponseEvent,
                                             ResponseEndEvent,
                                             ResponseStartEvent,
                                             ToolReturnEvent)
from bond.behaviours.behaviour_signal import InterruptSignal
from bond.behaviours.types import (IBehaviourEventHandler,
                                   IBehaviourSignalReceiver)
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import (AssistantMessage, FunctionCall,
                                     SystemMessage, TextChunk, ToolMessage,
                                     UsageInfo)
from bond.endpoints.summarization import SummarizationEndpoint
from bond.persona import Persona, SummarizationOptions
from bond.providers.provider import Provider
from bond.runtime import BondRuntime
from bond.tools.shell_tools import allow_shell_commands
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import Toolbox

logger = logging.getLogger(__name__)


def _do_tool_call(
    toolbox: Toolbox, function_call: FunctionCall, context: ToolCallContext
) -> str:
    result = toolbox.call_tool(function_call.name, function_call.arguments, context)
    logger.info(f"Tool call returned object of type {type(result)}\n{result}")
    if isinstance(result, Success):
        return result.unwrap()
    else:
        return f"Error during tool execution: {result.failure()}"


class SingleTurn:
    def __init__(
        self,
        persona: Persona,
        event_handler: IBehaviourEventHandler,
        signal_receiver: IBehaviourSignalReceiver,
        tool_call_context: ToolCallContext,
        stream: bool = False,
        allow_shell_executions: bool = False,
        max_retries: int = 10,
        runtime: BondRuntime | None = None,
    ):
        self.persona = persona
        self.event_handler = event_handler
        self.signal_receiver = signal_receiver
        self.tool_call_context = tool_call_context
        self.stream = stream
        self.allow_shell_executions = allow_shell_executions
        self.max_retries = max_retries
        self.runtime = runtime or BondRuntime.get_instance()

        self.provider: Provider = self.runtime.get_provider(persona.provider)
        self.toolbox = Toolbox(self.runtime.get_tools(persona.toolbox))
        self.tool_descriptions = self.toolbox.get_tool_descriptions()

        self.completions = self.provider.chat_completions()
        self.summary = self.provider.summarization()

        if stream and not self.completions.supports_streaming():
            raise RuntimeError(
                "The provider does not support streaming for chat completions"
            )

        if persona.summarization is not None and self.summary is None:
            logger.error(
                f"The provider does not support summarization while the persona {persona.name} expects it"
            )

    def run(self, conversation: Conversation) -> Conversation:
        while True:
            signal = self.signal_receiver.peek()
            if signal is not None and isinstance(signal, InterruptSignal):
                self.signal_receiver.get()
                return conversation

            system_msg = (
                SystemMessage.create(self.persona.system_prompt)
                if self.persona.system_prompt is not None
                else None
            )
            if self.stream:
                self.event_handler(
                    ResponseStartEvent(
                        author=self.persona.name or "Assistant", role="assistant"
                    )
                )
                response = self.completions.stream_chat_completion(
                    self.persona.model,
                    conversation.get_chat_completion_messages(),
                    tools=self.tool_descriptions,
                    callback=lambda chunk: self.event_handler(
                        AppendMessageChunkEvent(chunk=chunk)
                    ),
                    system_message=system_msg,
                    options=self.persona.model_options,
                    max_retries=self.max_retries,
                    conversation_metadata=conversation.metadata,
                )
                self.event_handler(ResponseEndEvent(usage=response.usage))
            else:
                response = self.completions.chat_completion(
                    self.persona.model,
                    conversation.get_chat_completion_messages(),
                    tools=self.tool_descriptions,
                    system_message=system_msg,
                    options=self.persona.model_options,
                    max_retries=self.max_retries,
                    conversation_metadata=conversation.metadata,
                )
                self.event_handler(
                    FullResponseEvent(
                        author=self.persona.name or "Assistant",
                        role="assistant",
                        response=response,
                    )
                )

            if len(response.choices) == 0:
                raise RuntimeError(f"Received empty response: {response}")
            message = response.choices[0].message
            conversation.add_message(
                ConversationMessage(
                    author=self.persona.name or self.persona.model,
                    message=AssistantMessage(
                        content=message.content, tool_calls=message.tool_calls
                    ),
                )
            )

            if (
                self.summary is not None
                and self.persona.summarization is not None
                and self.persona.summarization.auto_summarize
                and _check_summarize_condition(
                    self.persona.summarization, conversation, response.usage
                )
            ):
                _create_summary(
                    self.summary,
                    self.persona,
                    conversation,
                    response.usage,
                    self.max_retries,
                )
            conversation.current_usage = response.usage.total_tokens

            # Return when no tools are called
            if message.tool_calls is None:
                return conversation

            # Handle Tool calls
            for tool_call in message.tool_calls:
                self.event_handler(CallToolEvent(call=tool_call))
                if self.allow_shell_executions:
                    with allow_shell_commands():
                        result = _do_tool_call(
                            self.toolbox, tool_call.function, self.tool_call_context
                        )
                else:
                    result = _do_tool_call(
                        self.toolbox, tool_call.function, self.tool_call_context
                    )

                self.event_handler(ToolReturnEvent(result=result))
                conversation.add_message(
                    ConversationMessage.create_tool_response_message(result, tool_call)
                )


def _check_summarize_condition(
    summarization_options: SummarizationOptions | None,
    conversation: Conversation,
    usage: UsageInfo,
) -> bool:
    if summarization_options is None:
        return False
    n_unsummarized = (
        conversation.num_unsummarized_messages() - summarization_options.keep
    )
    if n_unsummarized > summarization_options.max_unsummarized_messages:
        return True
    if n_unsummarized < summarization_options.min_unsummarized_messages:
        return False
    if summarization_options.token_threshold is not None:
        return usage.total_tokens > summarization_options.token_threshold
    return False


def _create_summary(
    summarize: SummarizationEndpoint,
    persona: Persona,
    conversation: Conversation,
    usage: UsageInfo,
    max_retries: int,
):
    if persona.summarization is not None and _check_summarize_condition(
        persona.summarization, conversation, usage
    ):
        logger.debug("Performing summarization")
        summary_response = summarize.summarize(
            persona.summarization.model or persona.model,
            conversation.get_summary_messages(persona.summarization.keep),
            (
                SystemMessage(
                    content=[TextChunk(type="text", text=persona.summarization.prompt)]
                )
                if persona.summarization.prompt is not None
                else None
            ),
            persona.summarization.model_options or persona.model_options,
            max_retries,
            conversation.metadata,
        )
        summary = summary_response.choices[0].message
        if summary.tool_calls:
            logger.warning(
                "Summary call returned with tool calls. This is not expected and the tool calls will be discarded."
            )
        if summary.content is None:
            logger.warning("Summary call returned without content")
        summary_tool_msg = ToolMessage(
            content=[chunk for chunk in summary.content or []]
        )
        conversation.update_summary(summary_tool_msg, persona.summarization.keep)
        logger.debug("Updated summary")
