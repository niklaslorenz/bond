from typing import TextIO

from bond.conversation.types import (AssistantMessageChunk, TextChunk,
                                     ThinkChunk, ToolCall, UsageInfo)
from bond.endpoints.chat_completions import CompletionChunk, CompletionResponse


class StringAoe:
    _has_unfinished_text: bool = False
    _has_unfinished_thoughts: bool = False

    def __init__(
        self, text_out: TextIO | None = None, thought_out: TextIO | None = None
    ):
        self.text_out = text_out
        self.thought_out = thought_out

    def start_streaming_response(self, name: str | None):
        self._has_unfinished_text = True
        self._has_unfinished_thoughts = False
        self._handle_text(f"{name}:\n")

    def end_streaming_response(self, usage: UsageInfo | None):
        if self._has_unfinished_thoughts:
            self._handle_thought("\n")
        if self._has_unfinished_text:
            self._handle_text("\n\n")

    def handle_response_chunk(self, chunk: CompletionChunk):
        if len(chunk.choices) == 0:
            return
        content = chunk.choices[0].delta.content
        if content is not None:
            for content_chunk in content:
                self._handle_message_chunk(content_chunk)

    def handle_response(self, response: CompletionResponse):
        if len(response.choices) == 0:
            return
        message = response.choices[0].message
        if message.content is None:
            return
        for chunk in message.content:
            self._handle_message_chunk(chunk)

    def handle_tool_result(
        self,
        tool_call: ToolCall,
        tool_output: str,
    ):
        pass

    def _handle_text(self, text: str):
        if self.text_out is not None:
            self.text_out.write(text)

    def _handle_thought(self, thought: str):
        if self.thought_out is not None:
            self.thought_out.write(thought)

    def _handle_message_chunk(self, chunk: AssistantMessageChunk):
        if isinstance(chunk, TextChunk) and chunk.text != "":
            self._handle_text(chunk.text)
            self._has_unfinished_text = True
        if isinstance(chunk, ThinkChunk):
            for think_chunk in chunk.thinking:
                if isinstance(think_chunk, TextChunk) and think_chunk.text != "":
                    self._handle_thought(think_chunk.text)
                    self._has_unfinished_thoughts = True
