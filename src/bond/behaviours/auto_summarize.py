import logging

from returns.result import Result, Success

from bond.capabilities.summarization import (
    AutoSummarizationOptions,
    SummarizationCapability,
)
from bond.conversation.conversation import Conversation

logger = logging.getLogger(__name__)


class AutoSummarization:
    def __init__(
        self,
        summarize: SummarizationCapability,
    ):
        options = summarize.auto_summarization_options()
        self._config = options
        self._summarize = summarize

    def run(self, conversation: Conversation) -> Result[str | None, str]:
        if _check_summarize_condition(self._config, conversation):
            logger.debug("Performing automatic summarization")
            return self._summarize(conversation)
        else:
            logger.debug("Skipping automatic summarization")
            return Success(None)


def _check_summarize_condition(
    summarization_options: AutoSummarizationOptions | None,
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
