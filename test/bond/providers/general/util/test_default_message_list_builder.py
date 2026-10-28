"""Tests for bond.providers.general.util.default_message_list_builder module."""

from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    FrameworkConversationMessage,
    FunctionCall,
    TextChunk,
    ThinkChunk,
    ToolCall,
    ToolConversationMessage,
    ToolMessage,
    Turn,
    UsageInfo,
    UserConversationMessage,
    UserMessage,
)
from bond.providers.general.util.default_message_list_builder import (
    DefaultMessageListBuilder,
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


def make_user_message(text: str = "Hello") -> UserConversationMessage:
    return UserConversationMessage(
        message=UserMessage.create(text),
        name="user",
    )


def make_assistant_message(
    text: str = "Hi there",
    tool_calls: list[ToolCall] | None = None,
    condensed_thoughts: str | None = None,
    include_think_chunk: bool = False,
    name: str = "assistant",
) -> AssistantConversationMessage:
    content: list = []
    if include_think_chunk:
        content.append(ThinkChunk(thinking=[TextChunk(text="Original thoughts")]))
    if text is not None:
        content.append(TextChunk(text=text))

    return AssistantConversationMessage(
        message=AssistantMessage(
            content=content if content else None,
            tool_calls=tool_calls,
        ),
        name=name,
        condensed_thoughts=condensed_thoughts,
    )


def make_tool_message(
    text: str = "Tool result",
    name: str = "get_weather",
    tool_call_id: str = "call_123",
    tool_call_summary: str | None = None,
) -> ToolConversationMessage:
    return ToolConversationMessage(
        message=ToolMessage(
            name=name,
            tool_call_id=tool_call_id,
            content=[TextChunk(text=text)] if text is not None else None,
        ),
        tool_call_summary=tool_call_summary,
    )


def make_framework_message(
    content: str = "Framework content",
    name: str = "Framework",
) -> FrameworkConversationMessage:
    return FrameworkConversationMessage(
        content=content,
        name=name,
    )


def make_tool_call(
    name: str = "get_weather",
    arguments: dict | None = None,
    call_id: str = "call_123",
) -> ToolCall:
    return ToolCall(
        id=call_id,
        function=FunctionCall(name=name, arguments=arguments or {}),
    )


# ---------------------------------------------------------------------------
# DefaultMessageListBuilder - initialization
# ---------------------------------------------------------------------------


class TestDefaultMessageListBuilderInit:
    def test_default_parameters(self):
        builder = DefaultMessageListBuilder()
        assert builder._condensed is False
        assert builder._include_framework_messages is False

    def test_condensed_parameter(self):
        builder = DefaultMessageListBuilder(condensed=True)
        assert builder._condensed is True
        assert builder._include_framework_messages is False

    def test_include_framework_messages_parameter(self):
        builder = DefaultMessageListBuilder(include_framework_messages=True)
        assert builder._condensed is False
        assert builder._include_framework_messages is True

    def test_both_parameters(self):
        builder = DefaultMessageListBuilder(
            condensed=True, include_framework_messages=True
        )
        assert builder._condensed is True
        assert builder._include_framework_messages is True


# ---------------------------------------------------------------------------
# DefaultMessageListBuilder - render_user_message
# ---------------------------------------------------------------------------


class TestRenderUserMessage:
    def test_default_returns_original_message(self):
        builder = DefaultMessageListBuilder()
        msg = make_user_message("Hello world")
        result = builder.render_user_message(msg)
        assert len(result) == 1
        assert result[0] is msg.message

    def test_include_framework_messages_wraps_in_tags(self):
        builder = DefaultMessageListBuilder(include_framework_messages=True)
        msg = make_user_message("Hello world")
        result = builder.render_user_message(msg)
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)
        text = result[0].content[0].text
        assert text == "<user-message>\nHello world\n</user-message>\n"

    def test_include_framework_messages_escapes_html(self):
        builder = DefaultMessageListBuilder(include_framework_messages=True)
        msg = make_user_message("Hello <world> & friends")
        result = builder.render_user_message(msg)
        text = result[0].content[0].text
        assert "&lt;world&gt;" in text
        assert "&amp;" in text
        assert "<world>" not in text

    def test_include_framework_messages_with_multiple_chunks(self):
        builder = DefaultMessageListBuilder(include_framework_messages=True)
        msg = UserConversationMessage(
            message=UserMessage(
                content=[
                    TextChunk(text="Part 1 "),
                    TextChunk(text="Part 2"),
                ]
            ),
            name="user",
        )
        result = builder.render_user_message(msg)
        text = result[0].content[0].text
        assert "Part 1 Part 2" in text

    def test_include_framework_messages_with_empty_content(self):
        builder = DefaultMessageListBuilder(include_framework_messages=True)
        msg = UserConversationMessage(
            message=UserMessage(content=None),
            name="user",
        )
        result = builder.render_user_message(msg)
        text = result[0].content[0].text
        assert text == "<user-message>\n\n</user-message>\n"


# ---------------------------------------------------------------------------
# DefaultMessageListBuilder - render_tool_message
# ---------------------------------------------------------------------------


class TestRenderToolMessage:
    def test_default_returns_original_message(self):
        builder = DefaultMessageListBuilder()
        msg = make_tool_message("Sunny, 22°C")
        result = builder.render_tool_message(msg)
        assert len(result) == 1
        assert result[0] is msg.message

    def test_condensed_uses_tool_call_summary(self):
        builder = DefaultMessageListBuilder(condensed=True)
        msg = make_tool_message(
            "Full output here",
            tool_call_summary="Weather: sunny",
        )
        result = builder.render_tool_message(msg)
        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)
        assert result[0].content[0].text == "Weather: sunny"
        # Should preserve name and tool_call_id
        assert result[0].name == "get_weather"
        assert result[0].tool_call_id == "call_123"

    def test_condensed_without_summary_shows_truncated(self):
        builder = DefaultMessageListBuilder(condensed=True)
        msg = make_tool_message("Full output", tool_call_summary=None)
        result = builder.render_tool_message(msg)
        assert len(result) == 1
        assert result[0].content[0].text == "<tool output truncated>"

    def test_condensed_preserves_message_metadata(self):
        builder = DefaultMessageListBuilder(condensed=True)
        msg = make_tool_message(
            "output",
            name="custom_tool",
            tool_call_id="custom_id",
            tool_call_summary="summary",
        )
        result = builder.render_tool_message(msg)
        assert result[0].name == "custom_tool"
        assert result[0].tool_call_id == "custom_id"


# ---------------------------------------------------------------------------
# DefaultMessageListBuilder - render_assistant_message
# ---------------------------------------------------------------------------


class TestRenderAssistantMessage:
    def test_default_returns_original_message(self):
        builder = DefaultMessageListBuilder()
        msg = make_assistant_message("Hello!")
        result = builder.render_assistant_message(msg)
        assert len(result) == 1
        assert result[0] is msg.message

    def test_content_none_returns_original(self):
        builder = DefaultMessageListBuilder(condensed=True)
        msg = make_assistant_message(None)
        result = builder.render_assistant_message(msg)
        assert len(result) == 1
        assert result[0] is msg.message

    def test_condensed_removes_think_chunks(self):
        builder = DefaultMessageListBuilder(condensed=True)
        msg = make_assistant_message(
            "Answer",
            include_think_chunk=True,
        )
        result = builder.render_assistant_message(msg)
        assert len(result) == 1
        assert isinstance(result[0], AssistantMessage)
        # Should only have the text chunk, no ThinkChunk
        assert len(result[0].content) == 1
        assert isinstance(result[0].content[0], TextChunk)
        assert result[0].content[0].text == "Answer"

    def test_condensed_preserves_tool_calls(self):
        builder = DefaultMessageListBuilder(condensed=True)
        tool_calls = [make_tool_call("search", {"q": "test"})]
        msg = make_assistant_message(
            "Answer",
            tool_calls=tool_calls,
            include_think_chunk=True,
        )
        result = builder.render_assistant_message(msg)
        assert result[0].tool_calls is not None
        assert len(result[0].tool_calls) == 1
        assert result[0].tool_calls[0].function.name == "search"

    def test_condensed_thoughts_replaces_think_chunks(self):
        """When not condensed but has condensed_thoughts, ThinkChunks are replaced."""
        builder = DefaultMessageListBuilder(condensed=False)
        msg = make_assistant_message(
            "Answer",
            condensed_thoughts="Condensed thinking",
            include_think_chunk=True,
        )
        result = builder.render_assistant_message(msg)
        assert len(result) == 1
        assert isinstance(result[0], AssistantMessage)
        # Should have ThinkChunk with condensed thoughts + TextChunk
        assert len(result[0].content) == 2
        assert isinstance(result[0].content[0], ThinkChunk)
        assert result[0].content[0].thinking[0].text == "Condensed thinking"
        assert isinstance(result[0].content[1], TextChunk)
        assert result[0].content[1].text == "Answer"

    def test_condensed_thoughts_without_think_chunks(self):
        """When not condensed but has condensed_thoughts, ThinkChunk is prepended."""
        builder = DefaultMessageListBuilder(condensed=False)
        msg = make_assistant_message(
            "Answer",
            condensed_thoughts="Condensed thinking",
            include_think_chunk=False,
        )
        result = builder.render_assistant_message(msg)
        assert len(result) == 1
        assert len(result[0].content) == 2
        assert isinstance(result[0].content[0], ThinkChunk)
        assert result[0].content[0].thinking[0].text == "Condensed thinking"

    def test_no_condensed_thoughts_returns_original(self):
        """Without condensed_thoughts and not condensed, returns original."""
        builder = DefaultMessageListBuilder(condensed=False)
        msg = make_assistant_message(
            "Answer",
            condensed_thoughts=None,
            include_think_chunk=True,
        )
        result = builder.render_assistant_message(msg)
        assert len(result) == 1
        assert result[0] is msg.message

    def test_condensed_mode_with_condensed_thoughts(self):
        """In condensed mode, condensed_thoughts are ignored (ThinkChunks just removed)."""
        builder = DefaultMessageListBuilder(condensed=True)
        msg = make_assistant_message(
            "Answer",
            condensed_thoughts="Condensed thinking",
            include_think_chunk=True,
        )
        result = builder.render_assistant_message(msg)
        assert len(result) == 1
        # In condensed mode, only non-thought chunks remain
        assert len(result[0].content) == 1
        assert isinstance(result[0].content[0], TextChunk)


# ---------------------------------------------------------------------------
# DefaultMessageListBuilder - render_framework_message
# ---------------------------------------------------------------------------


class TestRenderFrameworkMessage:
    def test_default_returns_empty_list(self):
        builder = DefaultMessageListBuilder()
        msg = make_framework_message("Some content")
        result = builder.render_framework_message(msg)
        assert result == []

    def test_include_framework_messages_wraps_in_tags(self):
        builder = DefaultMessageListBuilder(include_framework_messages=True)
        msg = make_framework_message("System initialized")
        result = builder.render_framework_message(msg)
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)
        text = result[0].content[0].text
        assert text == "<framework-message>\nSystem initialized\n</framework-message>\n"

    def test_include_framework_messages_escapes_html(self):
        builder = DefaultMessageListBuilder(include_framework_messages=True)
        msg = make_framework_message("Content with <tags> & entities")
        result = builder.render_framework_message(msg)
        text = result[0].content[0].text
        assert "&lt;tags&gt;" in text
        assert "&amp;" in text
        assert "<tags>" not in text


# ---------------------------------------------------------------------------
# DefaultMessageListBuilder - render_message (dispatcher)
# ---------------------------------------------------------------------------


class TestRenderMessage:
    def test_dispatches_user_message(self):
        builder = DefaultMessageListBuilder()
        msg = make_user_message("Hello")
        result = builder.render_message(msg)
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)

    def test_dispatches_assistant_message(self):
        builder = DefaultMessageListBuilder()
        msg = make_assistant_message("Hi")
        result = builder.render_message(msg)
        assert len(result) == 1
        assert isinstance(result[0], AssistantMessage)

    def test_dispatches_tool_message(self):
        builder = DefaultMessageListBuilder()
        msg = make_tool_message("result")
        result = builder.render_message(msg)
        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)

    def test_dispatches_framework_message_default_excludes(self):
        builder = DefaultMessageListBuilder()
        msg = make_framework_message("content")
        result = builder.render_message(msg)
        assert result == []

    def test_dispatches_framework_message_includes(self):
        builder = DefaultMessageListBuilder(include_framework_messages=True)
        msg = make_framework_message("content")
        result = builder.render_message(msg)
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)


# ---------------------------------------------------------------------------
# DefaultMessageListBuilder - render_turn
# ---------------------------------------------------------------------------


class TestRenderTurn:
    def test_render_user_triggered_turn(self):
        builder = DefaultMessageListBuilder()
        turn = Turn(
            user_message=make_user_message("Hello"),
            assistant_response=make_assistant_message("Hi"),
            usage=make_usage(),
        )
        result = builder.render_turn(turn)
        assert len(result) == 2
        assert isinstance(result[0], UserMessage)
        assert isinstance(result[1], AssistantMessage)

    def test_render_tool_triggered_turn(self):
        builder = DefaultMessageListBuilder()
        turn = Turn(
            tool_messages=[make_tool_message("result", name="search")],
            assistant_response=make_assistant_message("Done"),
            usage=make_usage(),
        )
        result = builder.render_turn(turn)
        assert len(result) == 2
        assert isinstance(result[0], ToolMessage)
        assert isinstance(result[1], AssistantMessage)

    def test_render_turn_with_condensed_tool_message(self):
        builder = DefaultMessageListBuilder(condensed=True)
        turn = Turn(
            tool_messages=[
                make_tool_message("Full output", tool_call_summary="Brief output")
            ],
            assistant_response=make_assistant_message("Done"),
            usage=make_usage(),
        )
        result = builder.render_turn(turn)
        assert len(result) == 2
        assert isinstance(result[0], ToolMessage)
        assert result[0].content[0].text == "Brief output"

    def test_render_turn_flattens_all_messages(self):
        builder = DefaultMessageListBuilder()
        turn = Turn(
            tool_messages=[
                make_tool_message("result1", name="tool1"),
                make_tool_message("result2", name="tool2"),
            ],
            assistant_response=make_assistant_message("Done"),
            usage=make_usage(),
        )
        result = builder.render_turn(turn)
        assert len(result) == 3
        assert isinstance(result[0], ToolMessage)
        assert isinstance(result[1], ToolMessage)
        assert isinstance(result[2], AssistantMessage)


# ---------------------------------------------------------------------------
# DefaultMessageListBuilder - integration tests
# ---------------------------------------------------------------------------


class TestDefaultMessageListBuilderIntegration:
    def test_full_conversation_flow_default(self):
        """Test a complete flow in default mode."""
        builder = DefaultMessageListBuilder()

        user_msg = make_user_message("What's the weather?")
        result = builder.render_message(user_msg)
        assert result[0] is user_msg.message

        assistant_msg = make_assistant_message(
            "Let me check...",
            tool_calls=[make_tool_call("get_weather", {"city": "Berlin"})],
        )
        result = builder.render_message(assistant_msg)
        assert result[0] is assistant_msg.message

        tool_msg = make_tool_message("Sunny, 22°C")
        result = builder.render_message(tool_msg)
        assert result[0] is tool_msg.message

        final_msg = make_assistant_message("It's sunny!")
        result = builder.render_message(final_msg)
        assert result[0] is final_msg.message

    def test_full_conversation_flow_condensed(self):
        """Test a complete flow in condensed mode."""
        builder = DefaultMessageListBuilder(condensed=True)

        assistant_msg = make_assistant_message(
            "Answer",
            condensed_thoughts="Thinking...",
            include_think_chunk=True,
            tool_calls=[make_tool_call("search", {"q": "test"})],
        )
        result = builder.render_message(assistant_msg)
        # ThinkChunk should be removed in condensed mode
        assert len(result[0].content) == 1
        assert isinstance(result[0].content[0], TextChunk)
        # Tool calls should be preserved
        assert result[0].tool_calls is not None

        tool_msg = make_tool_message(
            "Full output",
            tool_call_summary="Brief output",
        )
        result = builder.render_message(tool_msg)
        assert result[0].content[0].text == "Brief output"

    def test_include_framework_messages_full_flow(self):
        """Test including framework messages wraps user and framework messages."""
        builder = DefaultMessageListBuilder(include_framework_messages=True)

        user_msg = make_user_message("Hello")
        result = builder.render_message(user_msg)
        text = result[0].content[0].text
        assert text.startswith("<user-message>")
        assert text.endswith("</user-message>\n")

        framework_msg = make_framework_message("System ready")
        result = builder.render_message(framework_msg)
        text = result[0].content[0].text
        assert text.startswith("<framework-message>")
        assert text.endswith("</framework-message>\n")

        # Tool and assistant messages should not be wrapped
        tool_msg = make_tool_message("result")
        result = builder.render_message(tool_msg)
        assert result[0] is tool_msg.message

    def test_html_escaping_preserves_content(self):
        """Test that HTML special characters are properly escaped."""
        builder = DefaultMessageListBuilder(include_framework_messages=True)
        msg = make_user_message('Code: `if x < y && z > 0 { print("hi") }`')
        result = builder.render_user_message(msg)
        text = result[0].content[0].text
        # Original special chars should be escaped
        assert "&lt;" in text
        assert "&gt;" in text
        assert "&amp;&amp;" in text
        # Tags should be properly structured
        assert "<user-message>" in text
        assert "</user-message>" in text
