from bond.capabilities.types import ConversationRenderer
from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessageChunk,
    TextChunk,
    ThinkChunk,
    ToolCall,
    ToolConversationMessage,
    UserConversationMessage,
)


class MarkdownRenderer(ConversationRenderer[str]):
    def __init__(self, *, condensed: bool = False):
        super().__init__(lambda x: "".join(x))
        self._condensed = condensed

    def render_user_message(self, user_message: UserConversationMessage) -> str:
        content = [f"## {user_message.name} (User):\n"]
        content.extend(
            chunk.text
            for chunk in user_message.message.content or {}
            if isinstance(chunk, TextChunk)
        )
        return "".join(content)

    def render_assistant_message(
        self, assistant_message: AssistantConversationMessage
    ) -> str:
        content = [f"## {assistant_message.name} (Assistant):\n"]

        if self._condensed and assistant_message.condensed_thoughts is not None:
            content.append(_wrap_think_block(assistant_message.condensed_thoughts))
            content.extend(
                chunk.text
                for chunk in assistant_message.message.content or []
                if isinstance(chunk, TextChunk)
            )
        else:
            content.extend(
                filter(
                    None,
                    (
                        _render_assistant_chunk(chunk)
                        for chunk in assistant_message.message.content or []
                    ),
                )
            )
        content.extend(
            _render_tool_call(tool_call, self._condensed)
            for tool_call in assistant_message.message.tool_calls or []
        )
        return "".join(content)

    def render_tool_message(self, tool_message: ToolConversationMessage) -> str:
        content = [f"## {tool_message.name} (Tool):\n"]
        if self._condensed:
            content.append(tool_message.tool_call_summary or "<tool output truncated>")
        else:
            content.extend(
                chunk.text
                for chunk in tool_message.message.content or []
                if isinstance(chunk, TextChunk)
            )
        return "".join(content)


def _render_assistant_chunk(chunk: AssistantMessageChunk) -> str | None:
    if isinstance(chunk, TextChunk):
        return chunk.text
    if isinstance(chunk, ThinkChunk):
        return _wrap_think_block(
            "".join(c.text for c in chunk.thinking if isinstance(c, TextChunk))
        )
    return None


def _wrap_think_block(thought: str) -> str:
    return f"```thinking\n{thought}\n```"


def _render_tool_call(tool_call: ToolCall, condensed: bool) -> str:
    content = [f"### Tool Call: {tool_call.function.name}"]
    for parameter, param_value in tool_call.function.arguments.items():
        if condensed:
            content.append(f"- {parameter}: <parameter value truncated>")
        else:
            content.append(f"- {parameter}: {param_value}")
    return "".join(content)
