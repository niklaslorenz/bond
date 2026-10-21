from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantMessage,
    FunctionCall,
    Message,
    SystemMessage,
    TextChunk,
    ToolCall,
    ToolMessage,
)


class DefaultMessageListBuilder:

    def __call__(
        self,
        conversation: Conversation,
        system_message: str | None,
        turns: int | None = None,
    ) -> tuple[SystemMessage | None, list[Message]]:
        episode = conversation.last_episode

        context_sections: list[str] = []

        if conversation.working_set is not None and conversation.working_set.items:
            context_sections.append(
                "<working-set>\n"
                "<reliability>potentially outdated</reliability>\n"
                "<source>updated during summarization</source>\n"
                "<content>\n"
                f"{conversation.working_set.render()}\n"
                "</content>\n"
                "</working-set>"
            )

        if conversation.task_list is not None and len(conversation.task_list) > 0:
            context_sections.append(
                "<task-list>\n"
                "<reliability>imperfect</reliability>\n"
                "<source>self-maintained</source>\n"
                "<content>\n"
                f"{conversation.task_list.render()}\n"
                "</content>\n"
                "</task-list>"
            )

        if episode.prefix_summary is not None:
            context_sections.append(
                "<previous-context>\n"
                "<reliability>imperfect</reliability>\n"
                "<source>model generated</source>\n"
                "<content>\n"
                f"{episode.prefix_summary}\n"
                "</content>\n"
                "</previous-context>"
            )

        context_extension = "\n".join(context_sections) if context_sections else None

        if system_message is not None or context_extension is not None:
            system_prompt = (system_message or "") + (
                "\n\n" + context_extension if context_extension else ""
            )
        else:
            system_prompt = None
        system_prompt = (
            SystemMessage(content=[TextChunk(text=system_prompt)])
            if system_prompt is not None
            else None
        )

        messages = conversation.last_episode.render(turns)
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

        # When rendering a prefix of the episode (e.g. for summarization),
        # the cut may land right after an assistant message with tool calls
        # whose responses live in the excluded turns. Append mock tool
        # responses so the message list stays valid for the API.
        if turns is not None and messages:
            last = messages[-1]
            if isinstance(last, AssistantMessage) and last.tool_calls:
                messages.extend(
                    ToolMessage(
                        name=call.function.name,
                        tool_call_id=call.id,
                        content=[TextChunk(text="<tool output truncated>")],
                    )
                    for call in last.tool_calls
                )
        return system_prompt, messages
