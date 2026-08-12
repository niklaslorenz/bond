from datetime import datetime
from typing import Any, Literal, cast
from urllib.parse import urljoin

import requests
from pydantic import BaseModel

from bond.conversation.types import (
    AssistantMessage,
    ConversationMetadata,
    Message,
    SystemMessage,
    TextChunk,
    ThinkChunk,
    ToolCall,
    ToolMessage,
    UsageInfo,
    UserMessage,
)
from bond.endpoints.chat_completions import (
    ChatCompletionStreamCallback,
    CompletionChoice,
    CompletionResponse,
    FinishReason,
)
from bond.endpoints.model_options import merge_options
from bond.providers.ollama.config import OllamaConfig, OllamaModelOptions
from bond.tools.tool import Tool
from bond.util import http_retry_loop, resolve_api_key

from . import logger

_think_prefix = "<think>"
_think_suffix = "</think>"


class OllamaToolCall(BaseModel):
    name: str
    description: str
    arguments: dict[str, Any]

    @classmethod
    def from_tool_call(cls, call: ToolCall) -> "OllamaToolCall":
        # TODO: Implement
        raise NotImplementedError()

    def to_tool_call(self) -> ToolCall:
        # TODO: Implement
        raise NotImplementedError()


class OllamaMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    thinking: str | None = None
    images: list[str] | None = None
    tool_calls: list[OllamaToolCall] | None = None

    @classmethod
    def from_message(cls, msg: Message) -> "OllamaMessage":
        role = msg.role
        tool_calls = (
            (
                [OllamaToolCall.from_tool_call(call) for call in msg.tool_calls]
                if msg.tool_calls is not None
                else []
            )
            if isinstance(msg, AssistantMessage)
            else None
        )

        content = []
        think = []
        if msg.content is not None:
            for chunk in msg.content:
                if isinstance(chunk, TextChunk):
                    content.append(chunk.text)
                elif isinstance(chunk, ThinkChunk):
                    think.append(
                        "\n".join(
                            [c.text for c in chunk.thinking if isinstance(c, TextChunk)]
                        )
                    )
                else:
                    logger.warning(
                        f"Could not parse message chunk of type {type(chunk)} for provider Ollama"
                    )
        return OllamaMessage(
            role=role,
            content="\n".join(content),
            thinking="\n".join(think),
            images=None,
            tool_calls=tool_calls,
        )

    def to_message(self) -> Message:
        chunks: list[TextChunk | ThinkChunk] = (
            [ThinkChunk(thinking=[TextChunk(text=self.thinking)])]
            if self.thinking is not None
            else []
        )
        chunks.append(TextChunk(text=self.content))
        if self.role == "assistant":
            return AssistantMessage(
                role=self.role,
                content=list(chunks),
                tool_calls=(
                    [tool_call.to_tool_call() for tool_call in self.tool_calls]
                    if self.tool_calls is not None
                    else None
                ),
            )
        elif self.role == "system":
            return SystemMessage(role=self.role, content=list(chunks))
        elif self.role == "tool":
            return ToolMessage(
                role=self.role, name=None, tool_call_id=None, content=list(chunks)
            )
        elif self.role == "user":
            return UserMessage(role=self.role, content=list(chunks))
        else:
            raise NotImplementedError()


class OllamaResponse(BaseModel):
    model: str
    created_at: str
    message: OllamaMessage
    done: bool
    done_reason: str | None
    total_duration: int
    load_duration: int
    prompt_eval_count: int
    prompt_eval_duration: int
    eval_count: int
    eval_duration: int

    def to_response(self) -> CompletionResponse:
        return CompletionResponse(
            choices=[
                CompletionChoice(
                    finish_reason=cast(FinishReason, self.done_reason or "error"),
                    message=cast(AssistantMessage, self.message.to_message()),
                )
            ],
            created=int(datetime.fromisoformat(self.created_at).timestamp()),
            id=self.created_at,
            model=self.model,
            usage=UsageInfo(
                completion_tokens=self.eval_count,
                prompt_tokens=self.prompt_eval_count,
                total_tokens=self.eval_count + self.prompt_eval_count,
            ),
        )


class OllamaChatCompletions:
    def __init__(self, config: OllamaConfig):
        self.config = config
        self.headers = {"Content-Type": "application/json"}
        if config.api_key is not None:
            self.headers["Authorization"] = f"Bearer {resolve_api_key(config.api_key)}"

    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        system_message: SystemMessage | None = None,
        options: OllamaModelOptions | None = None,
        max_retries: int = 3,
        conversation_metadata: ConversationMetadata | None = None,
    ) -> CompletionResponse:
        if self.config.models is not None and model not in self.config.models:
            raise ValueError(f"This model is not whitelisted")
        merged_options = merge_options(
            OllamaModelOptions,
            [
                self.config.chat_completion_options,
                self.config.model_specific_chat_completion_options.get(model),
                options,
            ],
        )
        all_messages = (
            [system_message] if system_message is not None else []
        ) + messages
        all_messages = [OllamaMessage.from_message(msg) for msg in all_messages]
        payload = {
            "model": model,
            "messages": [msg.model_dump(exclude={"thinking"}) for msg in all_messages],
            "tools": [tool.model_dump() for tool in tools],
            **(merged_options.model_dump() if merged_options is not None else {}),
        }
        payload["stream"] = False
        response = http_retry_loop(
            lambda: requests.post(
                urljoin(self.config.base_url, "api/chat"),
                headers=self.headers,
                json=payload,
                stream=False,
            ),
            max_retries=max_retries,
        )
        ollama_response = OllamaResponse.model_validate(response.json())
        return ollama_response.to_response()

    def stream_chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        callback: ChatCompletionStreamCallback,
        system_message: SystemMessage | None = None,
        options: OllamaModelOptions | None = None,
        max_retries: int = 3,
        conversation_metadata: ConversationMetadata | None = None,
    ) -> CompletionResponse:
        raise NotImplementedError()

    def supports_streaming(self) -> bool:
        return False
