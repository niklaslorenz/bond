from typing import Protocol

from returns.result import Result

from bond.conversation.conversation import Conversation


class ThoughtCondensationCapability(Protocol):
    def condense_thoughts(
        self, conversation: Conversation, force: bool
    ) -> Result[str | None, str]:
        """
        Create a compacted version of the thought traces of the last turn
        and add it to the assistant response

        Args:
            conversation (Conversation): the conversation to analyze
            force (bool): whether to condense the thought trace regardless of size

        Returns:
            None: if thought condensation is not supported
            Success:
                str: the compacted thought trace
                None: if there was no condensation
            Failure: an explaination, when the condensation failed
        """
        ...
