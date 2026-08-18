from typing import Type

from bond.conversation.types import (Message, ReferenceChunk, TextChunk,
                                     ThinkChunk, ToolReferenceChunk)
from bond.providers.ollama.chat_completions import OllamaChatCompletions
from bond.providers.ollama.config import OllamaConfig
from bond.providers.ollama.models import OllamaModels


def _parse_text_like_chunks(
    chunk: TextChunk | ReferenceChunk | ToolReferenceChunk | ThinkChunk,
) -> TextChunk:
    if isinstance(chunk, TextChunk):
        return chunk
    if isinstance(chunk, ReferenceChunk):
        return TextChunk(
            text="<references: "
            + ", ".join([str(ref) for ref in chunk.reference_ids])
            + ">"
        )
    if isinstance(chunk, ToolReferenceChunk):
        return TextChunk(
            text=f"<tool_call_reference: {chunk.title}, {chunk.tool}, {chunk.description}>"
        )
    if isinstance(chunk, ThinkChunk):
        chunks = [_parse_text_like_chunks(c).text for c in chunk.thinking]
        return TextChunk(text="<think>" + "\n".join(chunks) + "</think>")


def _parse_message(message: Message) -> Message:
    content = (
        [_parse_text_like_chunks(c) for c in message.content]
        if message.content is not None
        else None
    )
    message_fields = message.model_dump()
    message_fields["content"] = content
    return type(message).model_validate(message_fields)


class Ollama:
    def __init__(self, config: OllamaConfig):
        self.config = config
        self._models = OllamaModels(config)
        self._chat_completions = OllamaChatCompletions(config)

    def models(self) -> OllamaModels:
        return self._models

    def chat_completions(self) -> OllamaChatCompletions:
        return self._chat_completions

    @classmethod
    def get_config_type(cls) -> Type[OllamaConfig]:
        return OllamaConfig

    @classmethod
    def from_config(cls, config: OllamaConfig):
        return Ollama(config)
