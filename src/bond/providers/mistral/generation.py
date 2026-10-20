"""Mistral-specific generation capability with prompt caching support."""

from typing import Any, Callable
from uuid import uuid4

from returns.result import Result

from bond.capabilities.generation import GenerationTriggers
from bond.capabilities.types import MessageListBuilder
from bond.conversation.conversation import Conversation
from bond.conversation.types import AssistantConversationMessage
from bond.endpoints.chat_completions import CompletionChunk
from bond.providers.general.generation import (
    DefaultGenerationCapability,
    DefaultGenerationOptions,
)
from bond.providers.mistral.chat_completions import MistralChatCompletions
from bond.tools.tool import Tool


class MistralGeneration(DefaultGenerationCapability):
    """Generation capability for Mistral with prompt caching support.

    This class extends :class:`DefaultGenerationCapability` to inject the
    ``prompt_cache_key`` into the model options before calling the Mistral
    chat completions endpoint. The cache key is stored in the conversation's
    metadata so it persists across multiple generation calls.
    """

    def __init__(
        self,
        name: str,
        options: DefaultGenerationOptions,
        tools: list[Tool],
        chat_completions: MistralChatCompletions,
        max_retries: int,
        message_list_builder: MessageListBuilder,
    ):
        super().__init__(
            name, options, tools, chat_completions, max_retries, message_list_builder
        )

    def generate(
        self,
        conversation: Conversation,
        triggers: GenerationTriggers,
        callback: Callable[[CompletionChunk], None] | None,
        model_options: dict[str, Any] | None = None,
    ) -> Result[AssistantConversationMessage, str]:
        # Get or generate the cache key
        cache_key = conversation.metadata.mistral_cache_key
        if cache_key is None:
            cache_key = str(uuid4())
            conversation.metadata.mistral_cache_key = cache_key

        # Inject the cache key into model options
        mistral_options: dict[str, Any] = {
            **(model_options or {}),
            "prompt_cache_key": cache_key,
        }

        return super().generate(conversation, triggers, callback, mistral_options)
