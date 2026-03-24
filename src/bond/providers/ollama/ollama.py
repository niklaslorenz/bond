from typing import Any, Literal
from urllib.parse import urljoin

import requests
from pydantic import BaseModel
from smolagents.tools import get_json_schema

from bond.conversation.types import (Message, ReferenceChunk, TextChunk,
                                     ThinkChunk, ToolReferenceChunk)
from bond.endpoints.model_options import ModelOptions
from bond.tools.tool import ToolFn
from bond.util import resolve_api_key


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


class OllamaAPI:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
    ):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        if api_key is not None:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **additional_fields,
    ) -> requests.Response:
        payload = {
            "model": model,
            "messages": [_parse_message(msg).model_dump() for msg in messages],
            "tools": tools,
            **additional_fields,
        }
        response = requests.post(
            urljoin(self.base_url, "v1/chat/completions"),
            headers=self.headers,
            json=payload,
        )
        return response

    def retrieve_model(self, id: str) -> requests.Response:
        response = requests.get(
            urljoin(self.base_url, f"model/{id}"),
            headers=self.headers,
        )
        return response

    def list_models(self) -> requests.Response:
        response = requests.get(urljoin(self.base_url, "models"), headers=self.headers)
        return response

    @classmethod
    def create(cls, base_url: str, api_key: str | None = None) -> "OllamaAPI":
        return OllamaAPI(api_key=api_key or "", base_url=base_url)


class Ollama:
    def __init__(self, base_url: str, api_key: str | None = None):
        self.api = OllamaAPI.create(base_url, api_key)
        self._models = OllamaModels(self.api)
        self._chat_completions = OllamaChatCompletions[OllamaChatCompletionOptions](
            self.api, arguments_type=OllamaChatCompletionOptions
        )

    def models(self) -> OllamaModels:
        return self._models

    def chat_completions(self) -> OllamaChatCompletions:
        return self._chat_completions

    def parse_tool(self, tool: ToolFn) -> tuple[str, dict[str, Any]]:
        raw = get_json_schema(tool)
        if "return" in raw["function"]:
            raw["function"].pop("return")
        return raw["function"]["name"], raw
