"""Tests for bond.providers.general.util module."""

from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    FunctionCall,
    TextChunk,
    ToolCall,
    ToolConversationMessage,
    ToolMessage,
    Turn,
    UsageInfo,
    UserConversationMessage,
    UserMessage,
)
from bond.providers.general.util import DefaultMessageListBuilder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_usage(total_tokens: int = 30) -> UsageInfo:
    return UsageInfo(completion_tokens=10, prompt_tokens=20, total_tokens=total_tokens)


def make_text_turn(user_text: str, assistant_text: str) -> Turn:
    return Turn(
        user_message=UserConversationMessage(
            message=UserMessage.create(user_text),
            name="user",
        ),
        assistant_response=AssistantConversationMessage(
            message=AssistantMessage(content=[TextChunk(text=assistant_text)]),
            name="assistant",
            usage=make_usage(),
        ),
    )


def make_tool_call_turn(user_text: str, call_id: str = "call_1") -> Turn:
    return Turn(
        user_message=UserConversationMessage(
            message=UserMessage.create(user_text),
            name="user",
        ),
        assistant_response=AssistantConversationMessage(
            message=AssistantMessage(
                content=[TextChunk(text="Let me search...")],
                tool_calls=[
                    ToolCall(
                        id=call_id,
                        function=FunctionCall(name="search", arguments={"q": "test"}),
                    )
                ],
            ),
            name="assistant",
            usage=make_usage(),
        ),
    )


def make_tool_response_turn(call_id: str = "call_1", result: str = "found it") -> Turn:
    return Turn(
        tool_messages=[
            ToolConversationMessage(
                message=ToolMessage(
                    tool_call_id=call_id,
                    name="search",
                    content=[TextChunk(text=result)],
                )
            )
        ],
        assistant_response=AssistantConversationMessage(
            message=AssistantMessage(content=[TextChunk(text="Done.")]),
            name="assistant",
            usage=make_usage(),
        ),
    )


def make_conversation(*turns: Turn) -> Conversation:
    conv = Conversation()
    for turn in turns:
        conv.add_turn(turn)
    return conv


def assert_tool_calls_balanced(messages):
    """Every assistant tool_call must be followed by a matching tool message."""
    pending: list[str | None] = []
    for msg in messages:
        if isinstance(msg, AssistantMessage) and msg.tool_calls:
            pending.extend(call.id for call in msg.tool_calls if call.id)
        elif isinstance(msg, ToolMessage):
            assert pending, f"tool message {msg.tool_call_id} without preceding call"
            assert (
                msg.tool_call_id in pending
            ), f"tool_call_id mismatch: {msg.tool_call_id} not in {pending}"
            pending.remove(msg.tool_call_id)
    assert not pending, f"dangling tool calls without responses: {pending}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDefaultMessageListBuilder:
    def test_prefix_ending_with_dangling_tool_calls_appends_mocks(self):
        # Turn 2's assistant emits tool calls; the responses live in turn 3
        # which is excluded from the prefix.
        conv = make_conversation(
            make_text_turn("hi", "hello"),
            make_tool_call_turn("search for x", call_id="call_abc"),
            make_tool_response_turn(call_id="call_abc"),
        )
        _, messages = DefaultMessageListBuilder()(conv, None, turns=2)

        assert_tool_calls_balanced(messages)
        # The last two messages must be the mock tool response
        mock = messages[-1]
        assert isinstance(mock, ToolMessage)
        assert mock.tool_call_id == "call_abc"
        assert mock.name == "search"

    def test_full_render_with_dangling_tool_calls_appends_mocks(self):
        # Even when rendering the whole episode, if the last assistant
        # message has tool calls (e.g. summarizer appends a user prompt
        # afterwards), mocks keep the list valid.
        conv = make_conversation(
            make_text_turn("hi", "hello"),
            make_tool_call_turn("search for x", call_id="call_xyz"),
        )
        _, messages = DefaultMessageListBuilder()(conv, None, turns=2)

        assert_tool_calls_balanced(messages)
        assert isinstance(messages[-1], ToolMessage)
        assert messages[-1].tool_call_id == "call_xyz"

    def test_no_mocks_when_turns_is_none(self):
        # Generation path: real tool responses are appended by the caller,
        # so the builder must not add mocks.
        conv = make_conversation(
            make_text_turn("hi", "hello"),
            make_tool_call_turn("search for x", call_id="call_1"),
        )
        _, messages = DefaultMessageListBuilder()(conv, None)

        assert not any(isinstance(m, ToolMessage) for m in messages)

    def test_no_mocks_when_prefix_ends_with_plain_assistant(self):
        conv = make_conversation(
            make_text_turn("hi", "hello"),
            make_text_turn("again", "hi again"),
            make_tool_call_turn("search", call_id="call_9"),
            make_tool_response_turn(call_id="call_9"),
        )
        _, messages = DefaultMessageListBuilder()(conv, None, turns=2)

        assert_tool_calls_balanced(messages)
        assert not any(isinstance(m, ToolMessage) for m in messages)

    def test_balanced_prefix_with_tool_cycle_stays_untouched(self):
        conv = make_conversation(
            make_tool_call_turn("search", call_id="call_1"),
            make_tool_response_turn(call_id="call_1"),
            make_text_turn("thanks", "you're welcome"),
        )
        _, messages = DefaultMessageListBuilder()(conv, None, turns=2)

        assert_tool_calls_balanced(messages)
        # Only the real tool message, no mocks
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "call_1"
        assert tool_msgs[0].content is not None
        assert isinstance(tool_msgs[0].content[0], TextChunk)
        assert tool_msgs[0].content[0].text == "found it"

    def test_multiple_tool_calls_get_multiple_mocks(self):
        turn = Turn(
            user_message=UserConversationMessage(
                message=UserMessage.create("do two things"),
                name="user",
            ),
            assistant_response=AssistantConversationMessage(
                message=AssistantMessage(
                    tool_calls=[
                        ToolCall(
                            id="call_a",
                            function=FunctionCall(name="read_file", arguments={}),
                        ),
                        ToolCall(
                            id="call_b",
                            function=FunctionCall(name="grep", arguments={}),
                        ),
                    ]
                ),
                name="assistant",
                usage=make_usage(),
            ),
        )
        conv = make_conversation(turn, make_tool_response_turn("call_a"))
        # Only fix call_a in the next turn; call_b stays dangling
        assert conv.last_episode.turns[1].tool_messages is not None
        conv.last_episode.turns[1].tool_messages.append(
            ToolConversationMessage(
                message=ToolMessage(
                    tool_call_id="call_b",
                    name="grep",
                    content=[TextChunk(text="matches")],
                )
            )
        )
        _, messages = DefaultMessageListBuilder()(conv, None, turns=1)

        assert_tool_calls_balanced(messages)
        mocks = [m for m in messages if isinstance(m, ToolMessage)]
        assert len(mocks) == 2
        assert {m.tool_call_id for m in mocks} == {"call_a", "call_b"}
