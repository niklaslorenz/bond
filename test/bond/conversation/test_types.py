"""Tests for bond.conversation.types module."""

import json

import pytest
from pydantic import ValidationError

from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    AssistantMessageChunk,
    BaseConversationMessage,
    ConversationMetadata,
    Episode,
    FunctionCall,
    ReferenceChunk,
    SystemMessage,
    SystemMessageChunk,
    TextChunk,
    ThinkChunk,
    ToolCall,
    ToolConversationMessage,
    ToolMessage,
    ToolMessageChunk,
    ToolReferenceChunk,
    Turn,
    UsageInfo,
    UserConversationMessage,
    UserMessage,
    UserMessageChunk,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def make_usage(
    completion_tokens: int = 10,
    prompt_tokens: int = 20,
    total_tokens: int = 30,
) -> UsageInfo:
    return UsageInfo(
        completion_tokens=completion_tokens,
        prompt_tokens=prompt_tokens,
        total_tokens=total_tokens,
    )


def make_user_message(text: str = "Hello") -> UserMessage:
    return UserMessage.create(text)


def make_assistant_message(
    text: str = "Hi there",
    tool_calls: list[ToolCall] | None = None,
) -> AssistantMessage:
    return AssistantMessage(
        content=[TextChunk(text=text)],
        tool_calls=tool_calls,
    )


def make_turn(
    user_text: str = "Hello",
    assistant_text: str = "Hi there",
    tool_calls: list[ToolCall] | None = None,
) -> Turn:
    return Turn(
        user_message=UserConversationMessage(
            message=make_user_message(user_text),
            name="user",
        ),
        assistant_response=AssistantConversationMessage(
            message=make_assistant_message(assistant_text, tool_calls),
            name="assistant",
            usage=make_usage(),
        ),
    )


# ---------------------------------------------------------------------------
# Chunk types
# ---------------------------------------------------------------------------


class TestTextChunk:
    def test_default_type(self):
        chunk = TextChunk(text="hello")
        assert chunk.type == "text"
        assert chunk.text == "hello"

    def test_serialization(self):
        chunk = TextChunk(text="hello")
        data = chunk.model_dump()
        assert data == {"type": "text", "text": "hello"}


class TestReferenceChunk:
    def test_creation(self):
        chunk = ReferenceChunk(reference_ids=[1, 2, 3])
        assert chunk.type == "reference"
        assert chunk.reference_ids == [1, 2, 3]

    def test_empty_reference_ids(self):
        chunk = ReferenceChunk(reference_ids=[])
        assert chunk.reference_ids == []


class TestToolReferenceChunk:
    def test_creation_with_all_fields(self):
        chunk = ToolReferenceChunk(
            title="Search Results",
            tool="web_search",
            description="Found 5 results",
            favicon="https://example.com/favicon.ico",
            url="https://example.com",
        )
        assert chunk.type == "tool_reference"
        assert chunk.title == "Search Results"
        assert chunk.tool == "web_search"
        assert chunk.description == "Found 5 results"
        assert chunk.favicon == "https://example.com/favicon.ico"
        assert chunk.url == "https://example.com"

    def test_optional_fields_default_to_none(self):
        chunk = ToolReferenceChunk(title="Search", tool="web_search")
        assert chunk.description is None
        assert chunk.favicon is None
        assert chunk.url is None


class TestThinkChunk:
    def test_creation_with_text_chunks(self):
        chunk = ThinkChunk(
            thinking=[
                TextChunk(text="Let me think..."),
                TextChunk(text="I need to consider..."),
            ]
        )
        assert chunk.type == "thinking"
        assert len(chunk.thinking) == 2
        assert all(isinstance(c, TextChunk) for c in chunk.thinking)

    def test_creation_with_mixed_chunks(self):
        chunk = ThinkChunk(
            thinking=[
                TextChunk(text="Thinking..."),
                ToolReferenceChunk(title="Tool", tool="some_tool"),
                ReferenceChunk(reference_ids=[1]),
            ]
        )
        assert len(chunk.thinking) == 3


# ---------------------------------------------------------------------------
# FunctionCall
# ---------------------------------------------------------------------------


class TestFunctionCall:
    def test_creation_with_dict_arguments(self):
        fc = FunctionCall(name="get_weather", arguments={"city": "Berlin"})
        assert fc.name == "get_weather"
        assert fc.arguments == {"city": "Berlin"}

    def test_arguments_string_converted_to_dict(self):
        """The validator should convert a JSON string to a dict."""
        fc = FunctionCall(
            name="get_weather",
            arguments='{"city": "Berlin", "units": "celsius"}',  # pyright: ignore[reportArgumentType]
        )
        assert isinstance(fc.arguments, dict)
        assert fc.arguments == {"city": "Berlin", "units": "celsius"}

    def test_arguments_serialized_to_json_string(self):
        """The serializer should convert the dict back to a JSON string."""
        fc = FunctionCall(name="get_weather", arguments={"city": "Berlin"})
        data = fc.model_dump()
        assert isinstance(data["arguments"], str)
        assert json.loads(data["arguments"]) == {"city": "Berlin"}

    def test_arguments_serialized_in_json_mode(self):
        fc = FunctionCall(name="get_weather", arguments={"city": "Berlin"})
        data = fc.model_dump(mode="json")
        assert isinstance(data["arguments"], str)
        assert json.loads(data["arguments"]) == {"city": "Berlin"}

    def test_invalid_json_string_raises(self):
        with pytest.raises(ValidationError):
            FunctionCall(
                name="test",
                arguments="not valid json {{{",  # pyright: ignore[reportArgumentType]
            )

    def test_empty_arguments(self):
        fc = FunctionCall(name="noop", arguments={})
        assert fc.arguments == {}
        data = fc.model_dump()
        assert json.loads(data["arguments"]) == {}


# ---------------------------------------------------------------------------
# ToolCall
# ---------------------------------------------------------------------------


class TestToolCall:
    def test_creation(self):
        tc = ToolCall(
            id="call_123",
            function=FunctionCall(name="get_weather", arguments={"city": "Berlin"}),
        )
        assert tc.type == "function"
        assert tc.id == "call_123"
        assert tc.function.name == "get_weather"

    def test_id_optional(self):
        tc = ToolCall(
            function=FunctionCall(name="noop", arguments={}),
        )
        assert tc.id is None


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class TestAssistantMessage:
    def test_creation_with_content_list(self):
        msg = AssistantMessage(content=[TextChunk(text="Hello")])
        assert msg.role == "assistant"
        assert msg.content is not None
        assert len(msg.content) == 1

    def test_content_string_converted_to_list(self):
        """The validator should convert a plain string to [TextChunk]."""
        msg = AssistantMessage(
            content="Hello world"  # pyright: ignore[reportArgumentType]
        )
        assert isinstance(msg.content, list)
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextChunk)
        assert msg.content[0].text == "Hello world"

    def test_content_none_allowed(self):
        msg = AssistantMessage(content=None)
        assert msg.content is None

    def test_tool_calls_none_allowed(self):
        msg = AssistantMessage(content=[TextChunk(text="Hi")], tool_calls=None)
        assert msg.tool_calls is None

    def test_with_tool_calls(self):
        msg = AssistantMessage(
            content=[TextChunk(text="Let me check...")],
            tool_calls=[
                ToolCall(
                    id="call_1",
                    function=FunctionCall(name="search", arguments={"q": "test"}),
                )
            ],
        )
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1


class TestUserMessage:
    def test_create_classmethod(self):
        msg = UserMessage.create("Hello there")
        assert msg.role == "user"
        assert msg.content is not None
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextChunk)
        assert msg.content[0].text == "Hello there"

    def test_creation_with_chunks(self):
        msg = UserMessage(
            content=[
                TextChunk(text="Part 1"),
                ReferenceChunk(reference_ids=[1, 2]),
            ]
        )
        assert msg.content is not None
        assert len(msg.content) == 2


class TestSystemMessage:
    def test_create_classmethod(self):
        msg = SystemMessage.create("You are a helpful assistant")
        assert msg.role == "system"
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextChunk)
        assert msg.content[0].text == "You are a helpful assistant"

    def test_content_string_converted_to_list(self):
        msg = SystemMessage(
            content="System prompt here"  # pyright: ignore[reportArgumentType]
        )
        assert isinstance(msg.content, list)
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextChunk)


class TestToolMessage:
    def test_creation(self):
        msg = ToolMessage(
            name="get_weather",
            tool_call_id="call_123",
            content=[TextChunk(text='{"temp": 22}')],
        )
        assert msg.role == "tool"
        assert msg.name == "get_weather"
        assert msg.tool_call_id == "call_123"

    def test_optional_fields(self):
        msg = ToolMessage(content=[TextChunk(text="result")])
        assert msg.name is None
        assert msg.tool_call_id is None


# ---------------------------------------------------------------------------
# UsageInfo & ConversationMetadata
# ---------------------------------------------------------------------------


class TestUsageInfo:
    def test_creation(self):
        usage = UsageInfo(
            completion_tokens=10,
            prompt_tokens=20,
            total_tokens=30,
        )
        assert usage.completion_tokens == 10
        assert usage.prompt_tokens == 20
        assert usage.total_tokens == 30

    def test_prompt_audio_seconds_optional(self):
        usage = UsageInfo(
            completion_tokens=10,
            prompt_tokens=20,
            total_tokens=30,
        )
        assert usage.prompt_audio_seconds is None


class TestConversationMetadata:
    def test_default_empty(self):
        meta = ConversationMetadata()
        assert meta.mistral_cache_key is None

    def test_with_cache_key(self):
        meta = ConversationMetadata(mistral_cache_key="abc123")
        assert meta.mistral_cache_key == "abc123"


# ---------------------------------------------------------------------------
# Conversation Messages
# ---------------------------------------------------------------------------


class TestBaseConversationMessage:
    def test_message_id_generated(self):
        msg = UserConversationMessage(
            message=make_user_message(),
            name="user",
        )
        assert msg.message_id is not None
        assert len(msg.message_id) > 0

    def test_timestamp_is_utc(self):
        msg = UserConversationMessage(
            message=make_user_message(),
            name="user",
        )
        assert msg.timestamp.tzinfo is not None
        # Should be UTC
        offset = msg.timestamp.utcoffset()
        assert offset is not None
        assert offset.total_seconds() == 0

    def test_custom_message_id(self):
        msg = UserConversationMessage(
            message=make_user_message(),
            name="user",
            message_id="custom-id-123",
        )
        assert msg.message_id == "custom-id-123"


class TestUserConversationMessage:
    def test_render(self):
        msg = UserConversationMessage(
            message=make_user_message("Hello"),
            name="user",
        )
        rendered = msg.render()
        assert isinstance(rendered, UserMessage)
        assert rendered.content is not None
        assert isinstance(rendered.content[0], TextChunk)
        assert rendered.content[0].text == "Hello"


class TestAssistantConversationMessage:
    def test_render_without_condense(self):
        """Without condense and without condensed_thoughts, returns original message."""
        msg = AssistantConversationMessage(
            message=make_assistant_message("Hello"),
            name="assistant",
            usage=make_usage(),
        )
        rendered = msg.render(condense=False)
        assert rendered.content is not None
        assert len(rendered.content) == 1

    def test_render_with_condense_removes_think_chunks(self):
        """Condensing should remove ThinkChunks from content."""
        msg = AssistantConversationMessage(
            message=AssistantMessage(
                content=[
                    ThinkChunk(thinking=[TextChunk(text="internal thought")]),
                    TextChunk(text="Hello"),
                ],
            ),
            name="assistant",
            usage=make_usage(),
        )
        rendered = msg.render(condense=True)
        assert rendered.content is not None
        # Only the TextChunk should remain
        assert len(rendered.content) == 1
        assert isinstance(rendered.content[0], TextChunk)
        assert rendered.content[0].text == "Hello"

    def test_render_with_condensed_thoughts(self):
        """Without condense but with condensed_thoughts, a ThinkChunk with the summary is prepended."""
        msg = AssistantConversationMessage(
            message=AssistantMessage(
                content=[
                    ThinkChunk(thinking=[TextChunk(text="long internal thought")]),
                    TextChunk(text="Hello"),
                ],
            ),
            name="assistant",
            usage=make_usage(),
            condensed_thoughts="Summary of thoughts",
        )
        rendered = msg.render(condense=False)
        assert rendered.content is not None
        assert len(rendered.content) == 2
        # First should be a ThinkChunk with the condensed thoughts
        assert isinstance(rendered.content[0], ThinkChunk)
        assert isinstance(rendered.content[0].thinking[0], TextChunk)
        assert rendered.content[0].thinking[0].text == "Summary of thoughts"
        # Second should be the TextChunk
        assert isinstance(rendered.content[1], TextChunk)

    def test_render_none_content(self):
        """If message content is None, render returns the message as-is."""
        msg = AssistantConversationMessage(
            message=AssistantMessage(content=None),
            name="assistant",
            usage=make_usage(),
        )
        rendered = msg.render(condense=True)
        assert rendered.content is None

    def test_render_preserves_tool_calls(self):
        """Tool calls should be preserved during rendering."""
        msg = AssistantConversationMessage(
            message=make_assistant_message(
                "Let me search",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        function=FunctionCall(name="search", arguments={"q": "test"}),
                    )
                ],
            ),
            name="assistant",
            usage=make_usage(),
        )
        rendered = msg.render(condense=True)
        assert rendered.tool_calls is not None
        assert len(rendered.tool_calls) == 1


class TestToolConversationMessage:
    def test_name_property(self):
        msg = ToolConversationMessage(
            message=ToolMessage(
                name="get_weather",
                tool_call_id="call_1",
                content=[TextChunk(text="result")],
            ),
        )
        assert msg.name == "get_weather"

    def test_render_without_condense(self):
        msg = ToolConversationMessage(
            message=ToolMessage(
                name="search",
                tool_call_id="call_1",
                content=[TextChunk(text="full result data")],
            ),
            tool_call_summary="Brief summary",
        )
        rendered = msg.render(condense=False)
        # Without condense, should return original message
        assert rendered.content is not None
        assert isinstance(rendered.content[0], TextChunk)
        assert rendered.content[0].text == "full result data"

    def test_render_with_condense_uses_summary(self):
        msg = ToolConversationMessage(
            message=ToolMessage(
                name="search",
                tool_call_id="call_1",
                content=[TextChunk(text="full result data")],
            ),
            tool_call_summary="Brief summary",
        )
        rendered = msg.render(condense=True)
        assert rendered.content is not None
        assert len(rendered.content) == 1
        assert isinstance(rendered.content[0], TextChunk)
        assert rendered.content[0].text == "Brief summary"

    def test_render_with_condense_no_summary_uses_placeholder(self):
        msg = ToolConversationMessage(
            message=ToolMessage(
                name="search",
                tool_call_id="call_1",
                content=[TextChunk(text="full result data")],
            ),
            tool_call_summary=None,
        )
        rendered = msg.render(condense=True)
        assert rendered.content is not None
        assert isinstance(rendered.content[0], TextChunk)
        assert rendered.content[0].text == "<tool output truncated>"

    def test_render_with_condense_preserves_name_and_tool_call_id(self):
        msg = ToolConversationMessage(
            message=ToolMessage(
                name="search",
                tool_call_id="call_1",
                content=[TextChunk(text="data")],
            ),
        )
        rendered = msg.render(condense=True)
        assert rendered.name == "search"
        assert rendered.tool_call_id == "call_1"


# ---------------------------------------------------------------------------
# Turn
# ---------------------------------------------------------------------------


class TestTurn:
    def test_creation_with_user_message(self):
        turn = make_turn()
        assert turn.user_message is not None
        assert turn.tool_messages is None
        assert turn.assistant_response is not None

    def test_creation_with_tool_messages(self):
        turn = Turn(
            tool_messages=[
                ToolConversationMessage(
                    message=ToolMessage(
                        name="search",
                        tool_call_id="call_1",
                        content=[TextChunk(text="result")],
                    ),
                )
            ],
            assistant_response=AssistantConversationMessage(
                message=make_assistant_message("Based on the results..."),
                name="assistant",
                usage=make_usage(),
            ),
        )
        assert turn.user_message is None
        assert turn.tool_messages is not None
        assert len(turn.tool_messages) == 1

    def test_requires_user_or_tool_messages(self):
        """A turn must have either a user message or tool messages."""
        with pytest.raises(ValidationError, match="user message or tool responses"):
            Turn(
                user_message=None,
                tool_messages=None,
                assistant_response=AssistantConversationMessage(
                    message=make_assistant_message(),
                    name="assistant",
                    usage=make_usage(),
                ),
            )

    def test_turn_id_generated(self):
        turn = make_turn()
        assert turn.turn_id is not None
        assert len(turn.turn_id) > 0

    def test_completed_at(self):
        turn = make_turn()
        assert turn.completed_at == turn.assistant_response.timestamp

    def test_ends_run_true_when_no_tool_calls(self):
        turn = make_turn(tool_calls=None)
        assert turn.ends_run is True

    def test_ends_run_false_when_tool_calls_present(self):
        turn = make_turn(
            tool_calls=[
                ToolCall(
                    id="call_1",
                    function=FunctionCall(name="search", arguments={"q": "test"}),
                )
            ]
        )
        assert turn.ends_run is False

    def test_is_user_triggered_true(self):
        turn = make_turn()
        assert turn.is_user_triggered is True

    def test_is_user_triggered_false(self):
        turn = Turn(
            tool_messages=[
                ToolConversationMessage(
                    message=ToolMessage(
                        name="search",
                        tool_call_id="call_1",
                        content=[TextChunk(text="result")],
                    ),
                )
            ],
            assistant_response=AssistantConversationMessage(
                message=make_assistant_message("Response"),
                name="assistant",
                usage=make_usage(),
            ),
        )
        assert turn.is_user_triggered is False

    def test_usage_property(self):
        turn = make_turn()
        assert turn.usage.total_tokens == 30

    def test_condensed_default_false(self):
        turn = make_turn()
        assert turn.condensed is False

    def test_condense_sets_flag(self):
        turn = make_turn()
        turn.condense()
        assert turn.condensed is True

    def test_render_user_triggered(self):
        turn = make_turn(user_text="Hello", assistant_text="Hi there")
        messages = turn.render()
        # Should have user message + assistant message
        assert len(messages) == 2
        assert isinstance(messages[0], UserMessage)
        assert isinstance(messages[1], AssistantMessage)

    def test_render_tool_triggered(self):
        turn = Turn(
            tool_messages=[
                ToolConversationMessage(
                    message=ToolMessage(
                        name="search",
                        tool_call_id="call_1",
                        content=[TextChunk(text="search results")],
                    ),
                )
            ],
            assistant_response=AssistantConversationMessage(
                message=make_assistant_message("Here are the results"),
                name="assistant",
                usage=make_usage(),
            ),
        )
        messages = turn.render()
        # Should have tool message + assistant message
        assert len(messages) == 2
        assert isinstance(messages[0], ToolMessage)
        assert isinstance(messages[1], AssistantMessage)

    def test_render_with_condensed(self):
        turn = make_turn()
        turn.condense()
        messages = turn.render()
        assert len(messages) == 2

    def test_flatten_user_triggered(self):
        turn = make_turn()
        flattened = turn.flatten()
        assert len(flattened) == 2
        assert isinstance(flattened[0], UserConversationMessage)
        assert isinstance(flattened[1], AssistantConversationMessage)

    def test_flatten_tool_triggered(self):
        turn = Turn(
            tool_messages=[
                ToolConversationMessage(
                    message=ToolMessage(
                        name="search",
                        tool_call_id="call_1",
                        content=[TextChunk(text="result")],
                    ),
                )
            ],
            assistant_response=AssistantConversationMessage(
                message=make_assistant_message("Response"),
                name="assistant",
                usage=make_usage(),
            ),
        )
        flattened = turn.flatten()
        assert len(flattened) == 2
        assert isinstance(flattened[0], ToolConversationMessage)
        assert isinstance(flattened[1], AssistantConversationMessage)


# ---------------------------------------------------------------------------
# Episode
# ---------------------------------------------------------------------------


class TestEpisode:
    def test_creation_defaults(self):
        ep = Episode()
        assert ep.episode_id is not None
        assert ep.prefix_summary is None
        assert ep.episode_summary is None
        assert ep.turns == []
        assert ep.summarized_at is None

    def test_is_finished_false_by_default(self):
        ep = Episode()
        assert ep.is_finished is False

    def test_is_finished_true_when_summary_set(self):
        ep = Episode(episode_summary="Summary of this episode")
        assert ep.is_finished is True

    def test_last_turn_none_when_empty(self):
        ep = Episode()
        assert ep.last_turn is None

    def test_last_turn_returns_last_turn(self):
        turn1 = make_turn(user_text="First")
        turn2 = make_turn(user_text="Second")
        ep = Episode(turns=[turn1, turn2])
        assert ep.last_turn is turn2

    def test_render_empty_episode(self):
        ep = Episode()
        messages = ep.render()
        assert messages == []

    def test_render_with_turns(self):
        turn = make_turn(user_text="Hello", assistant_text="Hi")
        ep = Episode(turns=[turn])
        messages = ep.render()
        assert len(messages) == 2  # user + assistant

    def test_render_with_turns_limit(self):
        turn1 = make_turn(user_text="First")
        turn2 = make_turn(user_text="Second")
        ep = Episode(turns=[turn1, turn2])
        # Only render first turn
        messages = ep.render(turns=1)
        assert len(messages) == 2  # only first turn's messages

    def test_flatten_empty_episode(self):
        ep = Episode()
        flattened = ep.flatten()
        assert flattened == []

    def test_flatten_with_turns(self):
        turn = make_turn()
        ep = Episode(turns=[turn])
        flattened = ep.flatten()
        assert len(flattened) == 2

    def test_flatten_with_turns_limit(self):
        turn1 = make_turn(user_text="First")
        turn2 = make_turn(user_text="Second")
        ep = Episode(turns=[turn1, turn2])
        flattened = ep.flatten(turns=1)
        assert len(flattened) == 2  # only first turn

    def test_episode_id_unique(self):
        ep1 = Episode()
        ep2 = Episode()
        assert ep1.episode_id != ep2.episode_id

    def test_serialization_roundtrip(self):
        """Episode should survive serialization/deserialization."""
        turn = make_turn(user_text="Test message")
        ep = Episode(
            prefix_summary="Previous context",
            episode_summary="This episode summary",
            turns=[turn],
        )
        data = ep.model_dump(mode="json")
        ep2 = Episode.model_validate(data)
        assert ep2.episode_id == ep.episode_id
        assert ep2.prefix_summary == "Previous context"
        assert ep2.episode_summary == "This episode summary"
        assert len(ep2.turns) == 1
