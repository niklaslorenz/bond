"""Pluggable summarizer functions for the default summarization capability.

A summarizer function turns the oldest turns of the active episode into a
single summary string. The capability (policy, archiving, side-effect
handlers) lives in ``bond.providers.general.summarization``; the *how* of
producing a summary is just a function injected into it.

To add a new summarization style, write a function with this signature and
pass it to ``DefaultSummarizationCapability`` (or register it in
:data:`SUMMARIZERS` if you want config-driven selection by name).
"""

import logging
from typing import TYPE_CHECKING, Protocol

from returns.result import Failure, Result, Success

from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    Message,
    TextChunk,
    UserMessage,
)
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.providers.general.util.markdown_renderer import MarkdownRenderer

if TYPE_CHECKING:
    from bond.capabilities.types import SystemMessageBuilder
    from bond.providers.general.summarization import SummaryHandlerOptions

logger = logging.getLogger(__name__)


class SummarizerFn(Protocol):
    """Turns the oldest *turns* of the active episode into a summary string."""

    def __call__(
        self,
        conversation: Conversation,
        turns: int | None,
        chat_completions: ChatCompletionsEndpoint,
        system_message_builder: "SystemMessageBuilder",
        options: "SummaryHandlerOptions",
    ) -> Result[str, str]: ...


def _extract_summary_text(response) -> Result[str, str]:
    """Pull the text content out of a chat completion response."""
    if response.choices[0].message.tool_calls is not None:
        logger.warning(
            "Summarization call generated tool calls which is unexpected.\n"
            + "\n".join(
                f"Function: {tool_call.function.name}\n"
                f"Parameters: {tool_call.function.arguments}"
                for tool_call in response.choices[0].message.tool_calls
            )
        )
    if (content := response.choices[0].message.content) is None:
        return Failure("Model returned with no content")
    summary = "".join(chunk.text for chunk in content if isinstance(chunk, TextChunk))
    if summary == "":
        return Failure("Model returned with no content")
    return Success(summary)


def bulk_markdown_summary(
    conversation: Conversation,
    turns: int | None,
    chat_completions: ChatCompletionsEndpoint,
    system_message_builder: "SystemMessageBuilder",
    options: "SummaryHandlerOptions",
) -> Result[str, str]:
    """Render the turns as one condensed markdown transcript and summarize it.

    Uses the system message builder so that the previous episode summary (and
    working set / task list, if enabled on the builder) is included — this is
    what makes summaries roll forward instead of replacing each other.
    """
    renderer = MarkdownRenderer(condensed=True)
    rendered = renderer.render_conversation(conversation, turns)

    system_message = system_message_builder.render_system_message(
        conversation, options.prompt
    )
    message_list: list[Message] = [UserMessage(content=[TextChunk(text=rendered)])]
    if options.instruction:
        message_list.append(UserMessage(content=[TextChunk(text=options.instruction)]))

    response = chat_completions.chat_completion(
        options.model, message_list, [], system_message, options.model_options
    )
    return _extract_summary_text(response)


def chunked_markdown_summary(
    conversation: Conversation,
    turns: int | None,
    chat_completions: ChatCompletionsEndpoint,
    system_message_builder: "SystemMessageBuilder",
    options: "SummaryHandlerOptions",
) -> Result[str, str]:
    """Map-reduce summarization: summarize chunks of turns, then the summaries.

    Useful when a single episode is too large to summarize in one call.
    ``options.chunk_size`` controls how many turns go into each chunk.
    """
    renderer = MarkdownRenderer(condensed=True)
    system_message = system_message_builder.render_system_message(
        conversation, options.prompt
    )

    summarization_turns = conversation.last_episode.turns[slice(None, turns)]
    chunk_size = options.chunk_size or len(summarization_turns) or 1
    chunks: list[str] = []
    for start in range(0, len(summarization_turns), chunk_size):
        chunk_turns = summarization_turns[start : start + chunk_size]
        rendered = "".join(renderer.render_turn(turn) for turn in chunk_turns)
        response = chat_completions.chat_completion(
            options.model,
            [UserMessage(content=[TextChunk(text=rendered)])],
            [],
            system_message,
            options.model_options,
        )
        result = _extract_summary_text(response)
        if isinstance(result, Failure):
            return result
        chunks.append(result.unwrap())

    if len(chunks) <= 1:
        return Success(chunks[0]) if chunks else Failure("Nothing to summarize")

    # Reduce: summarize the chunk summaries into the final summary.
    combined = "\n\n---\n\n".join(chunks)
    message_list: list[Message] = [
        UserMessage(content=[TextChunk(text=combined)]),
    ]
    if options.instruction:
        message_list.append(UserMessage(content=[TextChunk(text=options.instruction)]))
    response = chat_completions.chat_completion(
        options.model, message_list, [], system_message, options.model_options
    )
    return _extract_summary_text(response)


#: Registry of built-in summarizers, for optional config-driven selection.
SUMMARIZERS: dict[str, SummarizerFn] = {
    "bulk_markdown": bulk_markdown_summary,
    "chunked_markdown": chunked_markdown_summary,
}
