import json
from typing import Any

import requests

from bond.conversation.types import SystemMessage
from bond.endpoints.chat_completions import (
    ChatCompletionStreamCallback,
    CompletionChunk,
    CompletionResponse,
    Message,
    Tool,
    build_response,
)
from bond.providers.mistral.config import MistralConfig
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
        options: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> CompletionResponse:
        if self.config.models is not None and model not in self.config.models:
            raise ValueError(f"This model is not whitelisted: {model}")
        merged_options = options or {}
        all_messages = (
            [system_message] if system_message is not None else []
        ) + messages
        payload = {
            "model": model,
            "messages": [msg.model_dump() for msg in all_messages],
            "tools": [tool.model_dump() for tool in tools],
            **merged_options,
        }
        response = http_retry_loop(
            lambda: requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=self.headers,
                json=payload,
                stream=False,
            ),
            max_retries=max_retries,
        )
        raw_data = response.json()
        parsed_response = CompletionResponse.model_validate(raw_data)
        if (
            cached_tokens := _extract_cached_tokens(raw_data.get("usage", {}))
        ) is not None:
            parsed_response.usage.num_cached_tokens = cached_tokens
        return parsed_response

    def stream_chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        callback: ChatCompletionStreamCallback,
        system_message: SystemMessage | None = None,
        options: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> CompletionResponse:
        if self.config.models is not None and model not in self.config.models:
            raise ValueError(f"Invalid model: {model}")
        merged_options = options or {}
        all_messages = (
            [system_message] if system_message is not None else []
        ) + messages
        payload = {
            "model": model,
            "messages": [msg.model_dump() for msg in all_messages],
            "tools": [tool.model_dump() for tool in tools],
            "stream": True,
            **merged_options,
        }
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
            raw_chunk = json.loads(event)
            chunk = CompletionChunk.model_validate(raw_chunk)
            if chunk.usage is not None:
                if (
                    cached_tokens := _extract_cached_tokens(raw_chunk.get("usage", {}))
                ) is not None:
                    chunk.usage.num_cached_tokens = cached_tokens
            chunks.append(chunk)
            callback(chunk)
        return build_response(chunks)

    def supports_streaming(self) -> bool:
        return True


def _extract_cached_tokens(raw_usage: dict[str, Any]) -> int | None:
    details = raw_usage.get("prompt_token_details") or raw_usage.get(
        "prompt_tokens_details"
    )
    if isinstance(details, dict):
        return details.get("cached_tokens")
    return None
