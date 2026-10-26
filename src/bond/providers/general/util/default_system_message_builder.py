from bond.capabilities.types import SystemMessageBuilder
from bond.conversation.conversation import Conversation
from bond.conversation.types import SystemMessage, TextChunk


class DefaultSystemMessageBuilder(SystemMessageBuilder):
    """
    System Message Builder that composes a prompt with context elements from the conversation, such as:
    - Episode Prefix Summary
    - Working Set
    - Task List
    """

    def __init__(
        self,
        *,
        include_prefix_summary: bool = False,
        include_working_set: bool = False,
        include_task_list: bool = False,
    ):
        self._include_prefix_summary = include_prefix_summary
        self._include_working_set = include_working_set
        self._include_task_list = include_task_list

    def render_system_message(
        self,
        conversation: Conversation,
        prompt: str | None,
    ) -> SystemMessage | None:
        episode = conversation.last_episode
        context_sections: list[str] = []
        if (
            self._include_working_set
            and conversation.working_set is not None
            and conversation.working_set.items
        ):
            context_sections.append(
                "<working-set>\n"
                "<reliability>potentially outdated</reliability>\n"
                "<source>updated during summarization</source>\n"
                "<content>\n"
                f"{conversation.working_set.render()}\n"
                "</content>\n"
                "</working-set>"
            )

        if (
            self._include_task_list
            and conversation.task_list is not None
            and len(conversation.task_list) > 0
        ):
            context_sections.append(
                "<task-list>\n"
                "<reliability>imperfect</reliability>\n"
                "<source>self-maintained</source>\n"
                "<content>\n"
                f"{conversation.task_list.render()}\n"
                "</content>\n"
                "</task-list>"
            )

        if self._include_prefix_summary and episode.prefix_summary is not None:
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
        if context_extension is not None and prompt is not None:
            system_prompt = prompt + "\n\n" + context_extension
        else:
            system_prompt = context_extension or prompt

        system_prompt = (
            SystemMessage(content=[TextChunk(text=system_prompt)])
            if system_prompt is not None
            else None
        )
        return system_prompt
