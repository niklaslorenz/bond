import logging
from typing import Any

from returns.result import Failure, Result, Success

from bond.conversation.types import (
    Message,
    SystemMessage,
    TextChunk,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import Toolbox

logger = logging.getLogger(__name__)


class ToolCallLoop:

    def __init__(self, toolbox: Toolbox, chat_completions: ChatCompletionsEndpoint):
        self._toolbox = toolbox
        self._chat_completions = chat_completions

    def run(
        self,
        model: str,
        model_options: dict[str, Any],
        message_list: list[Message],
        system_msg: SystemMessage,
        instruction: str,
        tool_context: ToolCallContext,
        max_iterations: int,
        max_retries: int = 3,
    ) -> Result[list[tuple[ToolCall, ToolMessage]], str]:
        """Run one maintenance step as a capped tool-calling loop.

        The instruction, every assistant message and every tool response are
        appended to the shared message list so subsequent calls (and steps)
        reuse the KV cache for the whole prefix.

        Returns Failure if the chat completions endpoint raises.
        """
        assert self._toolbox is not None  # guaranteed by the caller
        message_list.append(
            UserMessage(
                content=[
                    TextChunk(text=f"{instruction}\nAvailable Budget: {max_iterations}")
                ]
            )
        )
        tool_calls: list[tuple[ToolCall, ToolMessage]] = []
        for i in range(max_iterations):
            if i > 0:
                message_list.append(
                    UserMessage(
                        content=[
                            TextChunk(text=f"Available Budget: {max_iterations - i}")
                        ]
                    )
                )
            try:
                response = self._chat_completions.chat_completion(
                    model,
                    message_list,
                    self._toolbox.tool_descriptions,
                    system_msg,
                    model_options,
                    max_retries=max_retries,
                )
            except Exception as e:
                logger.error(f"Tool call loop endpoint error: {type(e).__name__}: {e}")
                return Failure(f"Endpoint error during tool call loop: {e}")
            message = response.choices[0].message
            message_list.append(message)
            if not message.tool_calls:
                return Success(tool_calls)
            for tool_call in message.tool_calls:
                result = self._toolbox.call_tool(
                    tool_call.function.name, tool_call.function.arguments, tool_context
                )
                output = (
                    result.unwrap()
                    if isinstance(result, Success)
                    else f"Failure: {result.failure()}"
                )
                tool_message = ToolMessage(
                    name=tool_call.function.name,
                    tool_call_id=tool_call.id,
                    content=[TextChunk(text=output)],
                )
                message_list.append(tool_message)
                tool_calls.append((tool_call, tool_message))
        logger.warning(
            f"Maintenance step reached the tool iteration cap ({max_iterations})"
        )
        return Success(tool_calls)
