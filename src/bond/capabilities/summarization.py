from typing import Protocol

from returns.result import Result

from bond.conversation.conversation import Conversation


class SummarizationCapability(Protocol):

    def summarize_episode(
        self, conversation: Conversation, force: bool
    ) -> Result[int, str]:
        """
        Summarize the current episode of a conversation and archive the summarized turns.

        Args:
            conversation (Conversation): the conversation to summarize
            force (bool): whether to summarize regardless of episode size

        Returns:
            None: if episode summarization is not supported
            Success: the number of archived turns, if the episode was summarized successfully
            Failure: an explanation, if the summarization failed
        """
        ...
