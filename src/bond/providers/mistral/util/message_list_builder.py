from bond.capabilities.types import ConversationRenderer
from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    FunctionCall,
    Message,
    TextChunk,
    ToolCall,
    ToolConversationMessage,
    ToolMessage,
    Turn,
)
from bond.providers.general.util.default_message_list_builder import (
    DefaultMessageListBuilder,
)


class MistralMessageListBuilder(DefaultMessageListBuilder):

    def __init__(
        self,
        *,
        condensed: bool = False,
        mock_starting_assistant_message: bool = False,
        mock_ending_tool_calls: bool = False,
    ):
        super().__init__(condensed=condensed)
        self._mock_starting_assistant_message = mock_starting_assistant_message
        self._mock_ending_tool_calls = mock_ending_tool_calls

    def render_conversation(
        self,
        conversation: Conversation,
        turns: int | slice | None = None,
    ) -> list[Message]:
        episode = conversation.last_episode

        rendered_turns = episode.turns[
            turns if isinstance(turns, slice) else slice(None, turns)
        ]

        messages = super().render_conversation(conversation, turns)

        if len(rendered_turns) > 0:
            if self._mock_starting_assistant_message:
                prefix = _create_assistant_message_mock(rendered_turns[0])
                if prefix is not None:
                    messages = self.render_assistant_message(prefix) + messages

            if self._mock_ending_tool_calls:
                suffix = _create_tool_call_mocks(rendered_turns[-1])
                if suffix is not None:
                    messages.extend(
                        sum((self.render_tool_message(msg) for msg in suffix), [])
                    )

        return messages


def _create_assistant_message_mock(
    first_turn: Turn,
) -> AssistantConversationMessage | None:
    if first_turn.tool_messages is None:
        return None
    mock_msg = AssistantMessage(
        tool_calls=[
            ToolCall(
                id=msg.message.tool_call_id,
                function=FunctionCall(
                    name=msg.name or "<unknown>",
                    arguments=msg.tool_call_parameters or {},
                ),
            )
            for msg in first_turn.tool_messages
        ]
    )
    mock = AssistantConversationMessage(
        message=mock_msg,
        name="Framework",
    )
    return mock


def _create_tool_call_mocks(last_turn: Turn) -> list[ToolConversationMessage] | None:

    if last_turn.assistant_response.message.tool_calls is None:
        return None
    return [
        ToolConversationMessage(
            message=ToolMessage(
                name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=[TextChunk(text="<tool output not available>")],
            ),
            tool_call_parameters=tool_call.function.arguments,
        )
        for tool_call in last_turn.assistant_response.message.tool_calls
    ]
