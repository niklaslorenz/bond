from typing import Protocol

from bond.conversation.conversation import Conversation
from bond.conversation.types import Message, SystemMessage


class MessageListBuilder(Protocol):
    def __call__(
        self,
        conversation: Conversation,
        system_message: str | None,
        turns: int | None = None,
    ) -> tuple[SystemMessage | None, list[Message]]: ...
