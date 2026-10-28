import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from bond.conversation.conversation import Conversation
from bond.conversation.types import SystemMessage, TextChunk, ThinkChunk, UserMessage
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.util import resolve_skills

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


class DefaultThoughtCondensationOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    prompt: str
    token_threshold: int

    def resolve(self, runtime: "BondRuntime | None"):
        self.prompt = resolve_skills(self.prompt, runtime)


class DefaultThoughtCondensationCapability:
    def __init__(
        self,
        config: DefaultThoughtCondensationOptions,
        chat_completions: ChatCompletionsEndpoint,
    ):
        self._config = config
        self._chat_completions = chat_completions

    def condense_thoughts(
        self, conversation: Conversation, force: bool
    ) -> Result[str | None, str]:
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
        if thought_token_estimate < self._config.token_threshold and not force:
            return Success(None)
        system_msg = SystemMessage(content=[TextChunk(text=self._config.prompt)])
        content_msg = UserMessage(content=[TextChunk(text=thoughts)])
        response = self._chat_completions.chat_completion(
            self._config.model,
            [content_msg],
            [],
            system_msg,
            self._config.model_options,
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
