from typing import Any, Callable

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from bond.capabilities.generation import GenerationTriggers
from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    FunctionCall,
    SystemMessage,
    TextChunk,
    ToolCall,
    UsageInfo,
)
from bond.endpoints.chat_completions import (
    ChatCompletionsEndpoint,
    CompletionChunk,
)
from bond.tools.tool import Tool


class DefaultGenerationOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    system_prompt: str | None


class DefaultGenerationCapability:
    def __init__(
        self,
        name: str,
        options: DefaultGenerationOptions,
        tools: list[Tool],
        chat_completions: ChatCompletionsEndpoint,
        max_retries: int,
    ):
        self._name = name
        self._options = options
        self._tools = tools
        self._chat_completions = chat_completions
        self._max_retries = max_retries

    def __call__(
        self,
        conversation: Conversation,
        triggers: GenerationTriggers,
        callback: Callable[[CompletionChunk], None] | None,
    ) -> Result[tuple[AssistantConversationMessage, UsageInfo], str]:
        can_stream = self._chat_completions.supports_streaming()
        should_stream = callback is not None
        if should_stream and not can_stream:
            return Failure("Streaming is not supported by the provided endpoint")

        # Verify trigger structure
        episode = conversation.episodes.last
        last_turn_tool_calls = (
            episode.turns[-1].assistant_response.message.tool_calls
            if episode.turns
            else []
        )
        called_tool_ids = (
            {call.id for call in last_turn_tool_calls}
            if last_turn_tool_calls is not None
            else set()
        )
        received_tool_response_ids = (
            {resp.message.tool_call_id for resp in triggers.tool_messages}
            if triggers.tool_messages is not None
            else set()
        )
        if called_tool_ids != received_tool_response_ids:
            return Failure(
                "Tool message triggers do not match the last turn's tool calls"
            )

        # Build System Message
        system_prompt = self._options.system_prompt
        summary_prompt_extension = (
            (
                "\n<previous-context>\n"
                "  <reliability>imperfect</reliability>\n"
                "  <source>model generated</source>\n"
                "  <content>\n"
                f"    {episode.prefix_summary}\n"
                "  </content>\n"
                "</previous-context>"
            )
            if episode.prefix_summary is not None
            else None
        )
        if system_prompt is not None or summary_prompt_extension is not None:
            system_prompt = (
                (system_prompt or "") + "\n" + (summary_prompt_extension or "")
            )

        system_message = (
            SystemMessage(content=[TextChunk(text=system_prompt)])
            if system_prompt is not None
            else None
        )

        # Build Message list
        messages = conversation.episodes.last.render()
        if episode.turns and episode.turns[0].tool_messages is not None:
            mock = AssistantMessage(
                tool_calls=[
                    ToolCall(
                        id=resp.message.tool_call_id,
                        function=FunctionCall(
                            name=resp.name, arguments=resp.tool_call_parameters or {}
                        ),
                    )
                    for resp in episode.turns[0].tool_messages
                ]
            )
            messages = [mock] + messages

        for tool_msg in triggers.tool_messages or []:
            messages.append(tool_msg.render(False))
        if triggers.user_message is not None:
            messages.append(triggers.user_message.render())

        # Generate response
        try:
            if should_stream:
                response = self._chat_completions.stream_chat_completion(
                    self._options.model,
                    messages,
                    self._tools,
                    callback,
                    system_message,
                    self._options.model_options,
                    self._max_retries,
                    conversation.metadata,
                )
            else:
                response = self._chat_completions.chat_completion(
                    self._options.model,
                    messages,
                    self._tools,
                    system_message,
                    self._options.model_options,
                    self._max_retries,
                    conversation.metadata,
                )
            if len(response.choices) == 0:
                return Failure(f"Received empty response from backend: {response}")
            message = response.choices[0].message
            conversation_message = AssistantConversationMessage(
                name=self._name, message=message
            )
            return Success((conversation_message, response.usage))
        except BaseException as e:
            return Failure(
                f"An exception occured during response generation: {type(e)}: {e}"
            )
