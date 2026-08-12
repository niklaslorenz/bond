from uuid import uuid4

import requests

from bond.conversation.types import ConversationMetadata, SystemMessage
from bond.endpoints.chat_completions import (
    ChatCompletionStreamCallback,
    CompletionChunk,
    CompletionResponse,
    Message,
    Tool,
    build_response,
)
from bond.endpoints.model_options import merge_options
from bond.providers.mistral.config import MistralConfig, MistralModelOptions
from bond.util import http_retry_loop, parse_sse_stream, resolve_api_key


class MistralChatCompletions:
    def __init__(
        self,
        config: MistralConfig,
    ):
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {resolve_api_key(config.api_key)}",
            "Content-Type": "application/json",
        }

    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        system_message: SystemMessage | None = None,
        options: MistralModelOptions | None = None,
        max_retries: int = 3,
        conversation_metadata: ConversationMetadata | None = None,
    ) -> CompletionResponse:
        if self.config.models is not None and model not in self.config.models:
            raise ValueError(f"This model is not whitelisted: {model}")
        merged_options = merge_options(
            MistralModelOptions,
            [
                self.config.chat_completion_options,
                self.config.model_specific_chat_completion_options.get(model),
                options,
            ],
        )
        all_messages = (
            [system_message] if system_message is not None else []
        ) + messages
        payload = {
            "model": model,
            "messages": [msg.model_dump() for msg in all_messages],
            "tools": [tool.model_dump() for tool in tools],
            **(merged_options.model_dump() if merged_options is not None else {}),
        }
        if (
            conversation_metadata is not None
            and conversation_metadata.mistral_cache_key is not None
        ):
            payload["prompt_cache_key"] = conversation_metadata.mistral_cache_key
        response = http_retry_loop(
            lambda: requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=self.headers,
                json=payload,
                stream=False,
            ),
            max_retries=max_retries,
        )
        if (
            conversation_metadata is not None
            and conversation_metadata.mistral_cache_key is None
        ):
            conversation_metadata.mistral_cache_key = _generate_cache_key()
        return CompletionResponse.model_validate(response.json())

    def stream_chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        callback: ChatCompletionStreamCallback,
        system_message: SystemMessage | None = None,
        options: MistralModelOptions | None = None,
        max_retries: int = 3,
        conversation_metadata: ConversationMetadata | None = None,
    ) -> CompletionResponse:
        if self.config.models is not None and model not in self.config.models:
            raise ValueError(f"Invalid model: {model}")
        merged_options = merge_options(
            MistralModelOptions,
            [
                self.config.chat_completion_options,
                self.config.model_specific_chat_completion_options.get(model),
                options,
            ],
        )
        all_messages = (
            [system_message] if system_message is not None else []
        ) + messages
        payload = {
            "model": model,
            "messages": [msg.model_dump() for msg in all_messages],
            "tools": [tool.model_dump() for tool in tools],
            "stream": True,
            **(merged_options.model_dump() if merged_options is not None else {}),
        }
        if (
            conversation_metadata is not None
            and conversation_metadata.mistral_cache_key is not None
        ):
            payload["prompt_cache_key"] = conversation_metadata.mistral_cache_key
        response = http_retry_loop(
            lambda: requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=self.headers,
                json=payload,
                stream=True,
            ),
            max_retries=max_retries,
        )
        chunks: list[CompletionChunk] = []
        for event in parse_sse_stream(response.iter_lines()):
            if event == "[DONE]":
                break
            chunk = CompletionChunk.model_validate_json(event)
            chunks.append(chunk)
            callback(chunk)
        if (
            conversation_metadata is not None
            and conversation_metadata.mistral_cache_key is None
        ):
            conversation_metadata.mistral_cache_key = _generate_cache_key()
        return build_response(chunks)

    def supports_streaming(self) -> bool:
        return True


def _generate_cache_key():
    return str(uuid4())
