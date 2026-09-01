from typing import Any, Protocol

from bond.conversation.conversation import Conversation
from bond.conversation.types import (ConversationMetadata, Message,
                                     SystemMessage, TextChunk, ToolMessage,
                                     UserMessage)
from bond.endpoints.chat_completions import CompletionResponse
from bond.persona import Persona

from . import logger


class SummarizationEndpoint(Protocol):

    def summarize(
        self,
        model: str,
        messages: list[Message],
        system_message: SystemMessage | None = None,
        options: dict[str, Any] | None = None,
        max_retries: int = 10,
        conversation_metadata: ConversationMetadata | None = None,
    ) -> CompletionResponse: ...


def summarize_conversation(
    summarize: SummarizationEndpoint,
    persona: Persona,
    conversation: Conversation,
    max_retries: int,
):
    if persona.summarization is not None:
        logger.debug("Performing summarization")
        messages = conversation.get_summary_messages(persona.summarization.keep)
        if persona.summarization.user_instruction is not None:
            messages.append(
                UserMessage(
                    content=[TextChunk(text=persona.summarization.user_instruction)]
                )
            )
        system_msg = (
            SystemMessage(
                content=[
                    TextChunk(
                        type="text",
                        text=(persona.summarization.system_prompt),
                    )
                ]
            )
            if persona.summarization.system_prompt is not None
            else None
        )
        summary_response = summarize.summarize(
            persona.summarization.model or persona.model,
            messages,
            system_msg,
            persona.summarization.model_options or persona.model_options,
            max_retries,
            conversation.metadata,
        )
        summary_msg = summary_response.choices[0].message
        if summary_msg.tool_calls:
            logger.warning(
                "Summary call returned with tool calls. This is not expected and the tool calls will be discarded."
            )
        if summary_msg.content is None:
            logger.warning("Summary call returned without content")
            return
        summary = "".join(
            chunk.text for chunk in summary_msg.content if isinstance(chunk, TextChunk)
        )
        conversation.update_summary(summary, persona.summarization.keep)
        logger.debug("Updated summary")
