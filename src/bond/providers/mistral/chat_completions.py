import functools
from collections import defaultdict

import requests
from pydantic import BaseModel

from bond.endpoints.chat_completions import (AssistantMessage,
                                             AssistantMessageChunk,
                                             ChatCompletionStreamCallback,
                                             CompletionChoice, CompletionChunk,
                                             CompletionResponse, FinishReason,
                                             Message, ReferenceChunk,
                                             TextChunk, ThinkChunk, Tool,
                                             ToolCall, UsageInfo)
from bond.endpoints.model_options import ModelOptions
from bond.providers.mistral.mistral import MistralConfig
from bond.util import http_retry_loop, resolve_api_key


class _MistralCompletionEvent(BaseModel):
    data: CompletionChunk


class MistralChatCompletionOptions(ModelOptions):
    temperature: float = 0.7


def _build_response(chunks: list[CompletionChunk]) -> CompletionResponse:
    if len(chunks) == 0:
        raise RuntimeError("Empty Response")
    tool_calls: dict[int, list[ToolCall]] = defaultdict(list)
    finish_reasons: dict[int, FinishReason] = {}
    content: dict[int, list[AssistantMessageChunk]] = defaultdict(list)

    usage_info: UsageInfo | None = None

    for chunk in chunks:
        if chunk.usage is not None:
            if usage_info is None:
                raise RuntimeError("Received duplicate usage info")
            usage_info = chunk.usage
        for choice in chunk.choices:
            idx = choice.index
            if choice.finish_reason is not None:
                if idx in finish_reasons:
                    raise RuntimeError("Received duplicate finish reason")
                finish_reasons[idx] = choice.finish_reason
            if choice.delta.tool_calls is not None:
                tool_calls[idx] += choice.delta.tool_calls
            if choice.delta.content is not None:
                content[idx].append(choice.delta.content)

    # Fold content
    def absorb_chunk[T](acc: list[T], content_chunk: T):
        if len(acc) == 0:
            acc.append(content_chunk)
            return acc
        last = acc[-1]

        if isinstance(last, TextChunk) and isinstance(content_chunk, TextChunk):
            last.text += content_chunk.text
            return acc

        if isinstance(last, ThinkChunk) and isinstance(content_chunk, ThinkChunk):
            if len(last.thinking) == 0:
                last.thinking = content_chunk.thinking
                return acc
            last.thinking = last.thinking[:-1] + functools.reduce(
                absorb_chunk, content_chunk.thinking, [last.thinking[-1]]
            )
            return acc

        if isinstance(last, ReferenceChunk) and isinstance(
            content_chunk, ReferenceChunk
        ):
            last.reference_ids += content_chunk.reference_ids
            return acc

        # No need to merge ToolReferenceChunks

        acc.append(content_chunk)
        return acc

    final_content: list[tuple[int, list[AssistantMessageChunk]]] = [
        (idx, functools.reduce(absorb_chunk, content_chunks, []))
        for idx, content_chunks in content.items()
    ]
    final_content.sort(key=lambda x: x[0])
    choices = [
        CompletionChoice(
            finish_reason=finish_reasons[idx],
            message=AssistantMessage(
                tool_calls=tool_calls[idx], content=content_chunks
            ),
        )
        for idx, content_chunks in final_content
    ]

    if usage_info is None:
        raise RuntimeError("No usage info received")

    return CompletionResponse(
        choices=choices,
        created=chunks[0].created,
        id=chunks[0].id,
        model=chunks[0].model,
        usage=usage_info,
    )


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
        options: MistralChatCompletionOptions,
        max_retries: int = 3,
    ) -> CompletionResponse:
        if self.config.models is not None and model not in self.config.models:
            raise ValueError(f"Invalid model: {model}")
        payload = {
            "model": model,
            "messages": [msg.model_dump() for msg in messages],
            "tools": [tool.model_dump() for tool in tools],
            **options.parse(),
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

    def stream_chat_completions(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        callback: ChatCompletionStreamCallback,
        options: MistralChatCompletionOptions,
        max_retries: int = 3,
    ) -> CompletionResponse:
        if self.config.models is not None and model not in self.config.models:
            raise ValueError(f"Invalid model: {model}")
        payload = {
            "model": model,
            "messages": [msg.model_dump() for msg in messages],
            "tools": [tool.model_dump() for tool in tools],
            "stream": True,
            **options.model_dump(),
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
        for line in response.iter_lines():
            chunk = _MistralCompletionEvent.model_validate_json(line)
            chunks.append(chunk.data)
            callback(chunk.data)
        return _build_response(chunks)

    def supports_streaming(self) -> bool:
        return True
