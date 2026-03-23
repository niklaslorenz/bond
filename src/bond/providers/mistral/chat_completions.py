import requests

from bond.endpoints.chat_completions import (ChatCompletionStreamCallback,
                                             CompletionChunk,
                                             CompletionResponse, Message, Tool,
                                             build_response)
from bond.endpoints.model_options import merge_options
from bond.providers.mistral.config import (MistralChatCompletionOptions,
                                           MistralConfig)
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
        options: MistralChatCompletionOptions | None = None,
        max_retries: int = 3,
    ) -> CompletionResponse:
        if self.config.models is not None and model not in self.config.models:
            raise ValueError(f"This model is not whitelisted: {model}")
        merged_options = merge_options(
            MistralChatCompletionOptions,
            [
                self.config.chat_completion_options,
                self.config.model_specific_chat_completion_options.get(model),
                options,
            ],
        )
        payload = {
            "model": model,
            "messages": [msg.model_dump() for msg in messages],
            "tools": [tool.model_dump() for tool in tools],
            **(merged_options.parse() if merged_options is not None else {}),
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
        return CompletionResponse.model_validate(response.json())

    def stream_chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        callback: ChatCompletionStreamCallback,
        options: MistralChatCompletionOptions | None = None,
        max_retries: int = 3,
    ) -> CompletionResponse:
        if self.config.models is not None and model not in self.config.models:
            raise ValueError(f"Invalid model: {model}")
        merged_options = merge_options(
            MistralChatCompletionOptions,
            [
                self.config.chat_completion_options,
                self.config.model_specific_chat_completion_options.get(model),
                options,
            ],
        )
        payload = {
            "model": model,
            "messages": [msg.model_dump() for msg in messages],
            "tools": [tool.model_dump() for tool in tools],
            "stream": True,
            **(merged_options.model_dump() if merged_options is not None else {}),
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
            chunk = CompletionChunk.model_validate_json(event)
            chunks.append(chunk)
            callback(chunk)
        return build_response(chunks)

    def supports_streaming(self) -> bool:
        return True
