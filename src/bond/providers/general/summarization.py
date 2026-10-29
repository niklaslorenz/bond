import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from bond.capabilities.types import MessageListBuilder, SystemMessageBuilder
from bond.conversation.conversation import Conversation
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.providers.general.summarization_fns import SummarizerFn
from bond.providers.general.util.tool_loop_runner import (
    ToolLoopRunner,
    ToolLoopRunnerOptions,
)
from bond.util import resolve_skills

if TYPE_CHECKING:
    from bond.runtime import BondRuntime

logger = logging.getLogger(__name__)


class SummaryHandlerOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    prompt: str
    instruction: str | None = None
    chunk_size: int | None = None

    def resolve(self, runtime: "BondRuntime | None"):
        self.prompt = resolve_skills(self.prompt, runtime)


class DefaultSummarizationOptions(BaseModel):
    token_threshold: int
    keep_turns: int
    min_summarized_turns: int
    task_list_handler: ToolLoopRunnerOptions | None = None
    working_set_handler: ToolLoopRunnerOptions | None = None
    summary_handler: SummaryHandlerOptions

    def resolve(self, runtime: "BondRuntime | None"):
        self.summary_handler.resolve(runtime)
        if self.task_list_handler is not None:
            self.task_list_handler.resolve(runtime)
        if self.working_set_handler is not None:
            self.working_set_handler.resolve(runtime)


class DefaultSummarizationCapability:

    def __init__(
        self,
        config: DefaultSummarizationOptions,
        chat_completions: ChatCompletionsEndpoint,
        message_list_builder: MessageListBuilder,
        system_message_builder: SystemMessageBuilder,
        summarization_strategy: SummarizerFn,
    ):
        self._config = config
        self._chat_completions = chat_completions
        self._message_list_builder = message_list_builder
        self._system_message_builder = system_message_builder
        self._summarization_strategy = summarization_strategy

        self._task_list_handler = (
            ToolLoopRunner(
                self._config.task_list_handler,
                chat_completions,
                system_message_builder,
                message_list_builder,
            )
            if self._config.task_list_handler is not None
            else None
        )
        self._working_set_handler = (
            ToolLoopRunner(
                self._config.working_set_handler,
                chat_completions,
                system_message_builder,
                message_list_builder,
            )
            if self._config.working_set_handler is not None
            else None
        )

    def summarize_episode(
        self, conversation: Conversation, force: bool
    ) -> Result[int, str]:

        last_turn = conversation.last_episode.last_turn
        if last_turn is None or (
            last_turn.usage.total_tokens < self._config.token_threshold and not force
        ):
            return Success(0)

        n_summarized_turns = (
            len(conversation.last_episode.turns) - self._config.keep_turns
        )
        if (
            n_summarized_turns < 0
            or n_summarized_turns < self._config.min_summarized_turns
        ):
            return Success(0)

        summary = self._summarization_strategy(
            conversation,
            n_summarized_turns,
            self._chat_completions,
            self._system_message_builder,
            self._config.summary_handler,
        )
        if isinstance(summary, Failure):
            return summary
        summary = summary.unwrap()

        if self._task_list_handler is not None:
            self._task_list_handler.run(conversation, n_summarized_turns)
        else:
            conversation.task_list = None
        if self._working_set_handler is not None:
            self._working_set_handler.run(conversation, n_summarized_turns)
        else:
            conversation.working_set = None

        if conversation.task_list is not None:
            conversation.task_list.update()
        if conversation.working_set is not None:
            conversation.working_set.update()
        conversation.archive_turns(n_summarized_turns, "", summary)
        return Success(n_summarized_turns)
