import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from bond.capabilities.types import MessageListBuilder, SystemMessageBuilder
from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    Message,
    SystemMessage,
    TextChunk,
    ThinkChunk,
    UserMessage,
)
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.providers.general.util.markdown_renderer import MarkdownRenderer
from bond.providers.general.util.tool_loop_runner import (
    ToolLoopRunner,
    ToolLoopRunnerOptions,
)
from bond.util import resolve_skills

if TYPE_CHECKING:
    from bond.runtime import BondRuntime

logger = logging.getLogger(__name__)


class ThoughtCondensationOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    prompt: str
    token_threshold: int

    def resolve(self, runtime: "BondRuntime | None"):
        self.prompt = resolve_skills(self.prompt, runtime)


class SummaryHandlerOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    prompt: str
    instruction: str


class EpisodeSummarizationOptions(BaseModel):
    token_threshold: int
    keep_turns: int
    min_summarized_turns: int
    task_list_handler: ToolLoopRunnerOptions | None = None
    working_set_handler: ToolLoopRunnerOptions | None = None
    summary_handler: SummaryHandlerOptions

    def resolve(self, runtime: "BondRuntime | None"):
        self.summary_handler.prompt = resolve_skills(
            self.summary_handler.prompt, runtime
        )
        if self.task_list_handler is not None:
            self.task_list_handler.resolve(runtime)
        if self.working_set_handler is not None:
            self.working_set_handler.resolve(runtime)


class DefaultSummarizationOptions(BaseModel):
    thought_condensation: ThoughtCondensationOptions | None = None
    episode_summarization: EpisodeSummarizationOptions | None = None

    def resolve(self, runtime: "BondRuntime | None"):
        if self.thought_condensation is not None:
            self.thought_condensation.resolve(runtime)
        if self.episode_summarization is not None:
            self.episode_summarization.resolve(runtime)


class DefaultSummarizationCapability:

    def __init__(
        self,
        config: DefaultSummarizationOptions,
        chat_completions: ChatCompletionsEndpoint,
        message_list_builder: MessageListBuilder,
        system_message_builder: SystemMessageBuilder,
    ):
        self._config = config
        self._chat_completions = chat_completions
        self._message_list_builder = message_list_builder
        self._system_message_builder = system_message_builder

        if (opts := self._config.episode_summarization) is not None:
            self._task_list_handler = (
                ToolLoopRunner(
                    opts.task_list_handler, chat_completions, message_list_builder
                )
                if opts.task_list_handler is not None
                else None
            )
            self._working_set_handler = (
                ToolLoopRunner(
                    opts.working_set_handler, chat_completions, message_list_builder
                )
                if opts.working_set_handler is not None
                else None
            )
        else:
            self._task_list_handler = None
            self._working_set_handler = None

    def summarize_episode(
        self, conversation: Conversation, force: bool
    ) -> Result[int, str] | None:
        if (options := self._config.episode_summarization) is None:
            return None

        last_turn = conversation.last_episode.last_turn
        if last_turn is None or (
            last_turn.usage.total_tokens < options.token_threshold and not force
        ):
            return Success(0)

        n_summarized_turns = len(conversation.last_episode.turns) - options.keep_turns
        if n_summarized_turns < 0 or n_summarized_turns < options.min_summarized_turns:
            return Success(0)

        summary = self._run_rendered_summarization(conversation, n_summarized_turns)
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

    def _run_rendered_summarization(
        self, conversation: Conversation, turns: int | None
    ) -> Result[str, str]:
        options = self._config.episode_summarization
        assert options is not None
        options = options.summary_handler
        renderer = MarkdownRenderer()

        rendered = renderer.render_conversation(conversation, turns)

        system_message = SystemMessage(content=[TextChunk(text=options.prompt)])
        message_list: list[Message] = [
            UserMessage(content=[TextChunk(text=rendered)]),
        ]

        response = self._chat_completions.chat_completion(
            options.model, message_list, [], system_message, options.model_options
        )
        if response.choices[0].message.tool_calls is not None:
            logger.warning(
                "Episode summarization call generated tool calls which is unexpected.\n"
                + "\n".join(
                    f"Function: {tool_call.function.name}\nParameters: {tool_call.function.arguments}"
                    for tool_call in response.choices[0].message.tool_calls
                )
            )
        if (content := response.choices[0].message.content) is None:
            return Failure("Model returned with no content")
        summary = "".join(
            [chunk.text for chunk in content if isinstance(chunk, TextChunk)]
        )
        if summary == "":
            return Failure("Model returned with no content")
        return Success(summary)

    def _run_summarization(
        self, conversation: Conversation, turns: int | None
    ) -> Result[str, str]:
        options = self._config.episode_summarization
        assert options is not None
        options = options.summary_handler

        message_list = self._message_list_builder.render_conversation(
            conversation, turns
        )
        system_msg = self._system_message_builder.render_system_message(
            conversation,
            options.prompt,
        )
        instruction_msg = UserMessage(content=[TextChunk(text=options.instruction)])
        message_list.append(instruction_msg)
        response = self._chat_completions.chat_completion(
            options.model,
            message_list,
            [],
            system_msg,
            options.model_options,
        )
        if response.choices[0].message.tool_calls is not None:
            logger.warning(
                "Episode summarization call generated tool calls which is unexpected.\n"
                + "\n".join(
                    f"Function: {tool_call.function.name}\nParameters: {tool_call.function.arguments}"
                    for tool_call in response.choices[0].message.tool_calls
                )
            )
        if (content := response.choices[0].message.content) is None:
            return Failure("Model returned with no content")
        summary = "".join(
            [chunk.text for chunk in content if isinstance(chunk, TextChunk)]
        )
        if summary == "":
            return Failure("Model returned with no content")
        return Success(summary)

    def condense_thoughts(
        self, conversation: Conversation, force: bool
    ) -> Result[str | None, str] | None:
        if (options := self._config.thought_condensation) is None:
            return None
        last_turn = conversation.last_episode.last_turn
        if last_turn is None:
            return Success(None)
        message = last_turn.assistant_response
        if message.message.content is None:
            return Success(None)
        thoughts = "".join(
            [
                tc.text
                for chunk in message.message.content
                if isinstance(chunk, ThinkChunk)
                for tc in chunk.thinking
                if isinstance(tc, TextChunk)
            ]
        )
        thought_token_estimate = len(thoughts) // 4
        if (
            thought_token_estimate < self._config.thought_condensation.token_threshold
            and not force
        ):
            return None
        system_msg = SystemMessage(content=[TextChunk(text=options.prompt)])
        content_msg = UserMessage(content=[TextChunk(text=thoughts)])
        response = self._chat_completions.chat_completion(
            options.model, [content_msg], [], system_msg, options.model_options
        )
        if response.choices[0].message.tool_calls is not None:
            logger.warning(
                "Thought condensation call generated tool calls which is unexpected."
            )
        if (content := response.choices[0].message.content) is None:
            return Failure("Model returned with no content")
        condensate = "".join(
            [chunk.text for chunk in content if isinstance(chunk, TextChunk)]
        )
        message.condensed_thoughts = condensate

        compression_ratio = len(condensate) / len(thoughts)
        new_completion_tokens = int(
            last_turn.usage.completion_tokens * compression_ratio
        )
        last_turn.usage.total_tokens = (
            last_turn.usage.total_tokens
            - last_turn.usage.completion_tokens
            + new_completion_tokens
        )
        last_turn.usage.completion_tokens = new_completion_tokens

        return Success(condensate)
