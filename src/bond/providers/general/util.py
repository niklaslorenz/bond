from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantMessage,
    FunctionCall,
    Message,
    SystemMessage,
    TextChunk,
    ToolCall,
)


class DefaultMessageListBuilder:

    def __call__(
        self,
        conversation: Conversation,
        system_message: str | None,
        turns: int | None = None,
    ) -> tuple[SystemMessage | None, list[Message]]:
        episode = conversation.episodes.last

        summary_prompt_extension = (
            (
                "\n<previous-context>\n"
                "  <reliability>imperfect</reliability>\n"
                "  <source>model generated</source>\n"
                "  <content>\n"
                f"    {episode.prefix_summary}\n"
                "  </content>\n"
                "</previous-context>"
            )
            if episode.prefix_summary is not None
            else None
        )
        if system_message is not None or summary_prompt_extension is not None:
            system_prompt = (
                (system_message or "") + "\n" + (summary_prompt_extension or "")
            )
        system_prompt = (
            SystemMessage(content=[TextChunk(text=system_prompt)])
            if system_prompt is not None
            else None
        )

        messages = conversation.episodes.last.render(turns)
        if episode.turns and episode.turns[0].tool_messages is not None:
            mock = AssistantMessage(
                tool_calls=[
                    ToolCall(
                        id=resp.message.tool_call_id,
                        function=FunctionCall(
                            name=resp.name or "<unknown>",
                            arguments=resp.tool_call_parameters or {},
                        ),
                    )
                    for resp in episode.turns[0].tool_messages
                ]
            )
            messages = [mock] + messages
        return system_prompt, messages
