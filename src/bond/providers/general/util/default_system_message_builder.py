import logging
from typing import TYPE_CHECKING

from returns.result import Success

from bond.capabilities.types import SystemMessageBuilder
from bond.conversation.conversation import Conversation
from bond.conversation.types import SystemMessage, TextChunk
from bond.skill import effective_available_skills, render_skill_md

if TYPE_CHECKING:
    from bond.persona import PersonaConfig
    from bond.runtime import BondRuntime

logger = logging.getLogger(__name__)


class DefaultSystemMessageBuilder(SystemMessageBuilder):
    """
    System Message Builder that composes a prompt with context elements from the conversation, such as:
    - Episode Prefix Summary
    - Working Set
    - Task List
    - Available / Active Skills
    """

    def __init__(
        self,
        *,
        include_prefix_summary: bool = False,
        include_working_set: bool = False,
        include_task_list: bool = False,
        include_skills: bool = False,
        runtime: "BondRuntime | None" = None,
    ):
        self._include_prefix_summary = include_prefix_summary
        self._include_working_set = include_working_set
        self._include_task_list = include_task_list
        self._include_skills = include_skills
        self._runtime = runtime

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

        if self._include_skills:
            context_sections.extend(self._render_skills_sections(conversation))

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

    def _render_skills_sections(self, conversation: Conversation) -> list[str]:
        """Render the <available-skills> and <active-skills> sections.

        Unknown skill names (not loadable via the runtime) are skipped with a
        warning instead of crashing the render.
        """
        runtime = self._runtime
        if runtime is None:
            # Function-local import: bond.runtime imports provider modules
            # (incl. this one) for the builtin builders, so a module-level
            # import would be circular.
            from bond.runtime import BondRuntime

            runtime = BondRuntime.get_instance()

        persona_config: PersonaConfig | None = None
        if conversation.persona is not None:
            result = runtime.get_persona(conversation.persona)
            if isinstance(result, Success):
                persona_config = result.unwrap()
            else:
                logger.warning(
                    f"Could not resolve persona '{conversation.persona}' for "
                    f"skill sections: {result.failure()}"
                )

        sections: list[str] = []

        available = effective_available_skills(conversation, persona_config)
        if available:
            lines = []
            for name in available:
                try:
                    skill = runtime.get_skill(name)
                    description = f": {skill.description}" if skill.description else ""
                    lines.append(f"- {name}{description}")
                except Exception as e:
                    logger.warning(f"Skipping unavailable skill '{name}': {e}")
            if lines:
                sections.append(
                    "<available-skills>\n"
                    "<reliability>trusted</reliability>\n"
                    "<source>user configuration</source>\n"
                    "<content>\n"
                    + "\n".join(lines)
                    + "\nUse the load_skill tool to activate a skill."
                    + "\n</content>\n"
                    "</available-skills>"
                )

        if conversation.active_skills:
            blocks = []
            for name in conversation.active_skills:
                if name not in available:
                    logger.warning(
                        f"Skipping active skill '{name}': not in the available skills"
                    )
                    continue
                try:
                    skill = runtime.get_skill(name)
                    blocks.append(render_skill_md(skill))
                except Exception as e:
                    logger.warning(f"Skipping active skill '{name}': {e}")
            if blocks:
                sections.append(
                    "<active-skills>\n"
                    "<reliability>trusted</reliability>\n"
                    "<source>user configuration</source>\n"
                    "<content>\n" + "\n\n".join(blocks) + "\n</content>\n"
                    "</active-skills>"
                )

        return sections
