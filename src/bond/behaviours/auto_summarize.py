from returns.result import Result, Success

from bond.conversation.conversation import Conversation
from bond.endpoints.chat_completions import CompletionResponse
from bond.persona import AutoSummarization
from bond.providers.provider import ConversationSummarizationStrategy

from . import logger


class AutoSummarize:
    def __init__(
        self,
        config: AutoSummarization,
        summarize: ConversationSummarizationStrategy,
        keep: int,
    ):
        self._config = config
        self._summarize = summarize
        self._keep = keep

    def run(self, conversation: Conversation) -> Result[CompletionResponse | None, str]:
        if _check_summarize_condition(self._config, conversation):
            logger.debug("Performing automatic summarization")
            return self._summarize(conversation)
        else:
            logger.debug("Skipping automatic summarization")
            return Success(None)


def _check_summarize_condition(
    summarization_options: AutoSummarization | None,
    conversation: Conversation,
) -> bool:
    if summarization_options is None:
        return False
    n_unsummarized = conversation.num_unsummarized_messages()
    if n_unsummarized > summarization_options.max_messages:
        return True
    if n_unsummarized < summarization_options.min_messages:
        return False
    if summarization_options.token_threshold is not None:
        return conversation.current_usage > summarization_options.token_threshold
    return False
