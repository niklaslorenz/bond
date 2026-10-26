from bond.capabilities.types import MessageListBuilder
from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    AssistantMessageChunk,
    Message,
    TextChunk,
    ThinkChunk,
    ToolConversationMessage,
    ToolMessage,
    UserConversationMessage,
)


class DefaultMessageListBuilder(MessageListBuilder):
    def __init__(self, *, condensed: bool = False):
        super().__init__(lambda x: sum(x, []))
        self._condensed = condensed

    def render_user_message(
        self, user_message: UserConversationMessage
    ) -> list[Message]:
        return [user_message.message]

    def render_tool_message(
        self, tool_message: ToolConversationMessage
    ) -> list[Message]:
        if not self._condensed:
            return [tool_message.message]
        return [
            ToolMessage(
                name=tool_message.message.name,
                tool_call_id=tool_message.message.tool_call_id,
                content=[
                    TextChunk(
                        text=tool_message.tool_call_summary or "<tool output truncated>"
                    )
                ],
            )
        ]

    def render_assistant_message(
        self, assistant_message: AssistantConversationMessage
    ) -> list[Message]:
        if assistant_message.message.content is None:
            return [assistant_message.message]
        if assistant_message.condensed_thoughts is None and not self._condensed:
            return [assistant_message.message]
        non_thoughts: list[AssistantMessageChunk] = [
            chunk
            for chunk in assistant_message.message.content
            if not isinstance(chunk, ThinkChunk)
        ]
        if self._condensed:
            return [
                AssistantMessage(
                    tool_calls=assistant_message.message.tool_calls,
                    content=non_thoughts,
                )
            ]
        assert assistant_message.condensed_thoughts is not None  # follows logically
        content = [
            ThinkChunk(thinking=[TextChunk(text=assistant_message.condensed_thoughts)])
        ] + non_thoughts
        return [
            AssistantMessage(
                tool_calls=assistant_message.message.tool_calls, content=content
            )
        ]
