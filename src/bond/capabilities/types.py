from abc import ABC, abstractmethod
from typing import Callable, Iterable

from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantConversationMessage,
    ConversationMessage,
    Message,
    SystemMessage,
    ToolConversationMessage,
    Turn,
    UserConversationMessage,
)


class ConversationRenderer[T](ABC):

    def __init__(self, composer: Callable[[Iterable[T]], T]):
        self._compose = composer

    @abstractmethod
    def render_user_message(self, user_message: UserConversationMessage) -> T: ...

    @abstractmethod
    def render_assistant_message(
        self, assistant_message: AssistantConversationMessage
    ) -> T: ...

    @abstractmethod
    def render_tool_message(self, tool_message: ToolConversationMessage) -> T: ...

    def render_message(self, message: ConversationMessage) -> T:
        if isinstance(message, UserConversationMessage):
            return self.render_user_message(message)
        if isinstance(message, AssistantConversationMessage):
            return self.render_assistant_message(message)
        if isinstance(message, ToolConversationMessage):
            return self.render_tool_message(message)

    def render_turn(self, turn: Turn) -> T:
        return self._compose([self.render_message(msg) for msg in turn.flatten()])

    def render_conversation(
        self, conversation: Conversation, turns: int | slice | None = None
    ) -> T:
        return self._compose(
            [
                self.render_message(msg)
                for msg in conversation.last_episode.flatten(turns)
            ]
        )


class SystemMessageBuilder(ABC):
    @abstractmethod
    def render_system_message(
        self,
        conversation: Conversation,
        prompt: str | None,
    ) -> SystemMessage | None: ...


MessageListBuilder = ConversationRenderer[list[Message]]
