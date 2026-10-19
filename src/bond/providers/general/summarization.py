import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from bond.capabilities.types import MessageListBuilder
from bond.conversation.conversation import Conversation
from bond.conversation.types import SystemMessage, TextChunk, ThinkChunk, UserMessage
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
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


class EpisodeSummarizationOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    prompt: str
    token_threshold: int
    keep_turns: int
    min_summarized_turns: int

    def resolve(self, runtime: "BondRuntime | None"):
        self.prompt = resolve_skills(self.prompt, runtime)


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
        system_prompt: str | None,
    ):
        self._config = config
        self._chat_completions = chat_completions
        self._message_list_builder = message_list_builder
        self._system_prompt = system_prompt

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

        system_msg, message_list = self._message_list_builder(
            conversation, self._system_prompt, n_summarized_turns
        )
        message_list.append(UserMessage(content=[TextChunk(text=options.prompt)]))
        response = self._chat_completions.chat_completion(
            options.model,
            message_list,
            [],
            system_msg,
            options.model_options,
            conversation_metadata=conversation.metadata,
        )
        if response.choices[0].message.tool_calls is not None:
            logger.warning(
                "Episode summarization call generated tool calls which is unexpected."
            )
        if (content := response.choices[0].message.content) is None:
            return Failure("Model returned with no content")
        summary = "".join(
            [chunk.text for chunk in content if isinstance(chunk, TextChunk)]
        )
        conversation.archive_turns(n_summarized_turns, "", summary)
        return Success(n_summarized_turns)

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
        new_completion_tokens = int(message.usage.completion_tokens * compression_ratio)
        message.usage.total_tokens = (
            message.usage.total_tokens
            - message.usage.completion_tokens
            + new_completion_tokens
        )
        message.usage.completion_tokens = new_completion_tokens

        return Success(condensate)
