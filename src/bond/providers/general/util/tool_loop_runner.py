import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from bond.capabilities.types import MessageListBuilder, SystemMessageBuilder
from bond.conversation.conversation import Conversation
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.providers.general.util import ToolCallLoop
from bond.tools.task_list import task_list_toolset
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import Toolbox
from bond.util import resolve_skills

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


class ToolLoopRunnerOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    system_prompt: str
    instruction: str
    iterations: int

    def resolve(self, runtime: "BondRuntime | None"):
        self.system_prompt = resolve_skills(self.system_prompt, runtime)
        self.instruction = resolve_skills(self.instruction, runtime)


logger = logging.getLogger(__name__)


class ToolLoopRunner:
    def __init__(
        self,
        options: ToolLoopRunnerOptions,
        chat_completions: ChatCompletionsEndpoint,
        system_message_builder: SystemMessageBuilder,
        message_list_builder: MessageListBuilder,
    ):
        self._options = options
        self._chat_completions = chat_completions
        self._system_message_builder = system_message_builder
        self._message_list_builder = message_list_builder
        self._toolbox = Toolbox([task_list_toolset])
        self._tool_call_loop = ToolCallLoop(self._toolbox, self._chat_completions)

    def run(self, conversation: Conversation, turns: int | None):
        system_message = self._system_message_builder.render_system_message(
            conversation, self._options.system_prompt
        )
        message_list = self._message_list_builder.render_conversation(
            conversation, turns
        )
        assert (
            system_message is not None
        )  # guaranteed because system prompt is not None
        tool_context = ToolCallContext(
            persona=None,
            stdout=None,
            stdin=None,
            is_interactive=False,
            cwd=None,
            logger=logger,
            confirmation_prompt=None,
            conversation=conversation,
        )
        self._tool_call_loop.run(
            self._options.model,
            self._options.model_options or {},
            message_list,
            system_message,
            self._options.instruction,
            tool_context,
            self._options.iterations,
        )
