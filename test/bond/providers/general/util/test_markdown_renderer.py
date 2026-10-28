"""Tests for bond.providers.general.util.markdown_renderer module."""

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
from bond.providers.general.util.markdown_renderer import (
    MarkdownRenderer,
    _render_assistant_chunk,
    _render_tool_call,
    _wrap_think_block,
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
    name: str = "assistant",
) -> AssistantConversationMessage:
    return AssistantConversationMessage(
        message=AssistantMessage(
            content=[TextChunk(text=text)] if text is not None else None,
            tool_calls=tool_calls,
        ),
        name=name,
        condensed_thoughts=condensed_thoughts,
    )


def make_tool_message(
    text: str = "Tool result",
    name: str = "get_weather",
    tool_call_summary: str | None = None,
) -> ToolConversationMessage:
    return ToolConversationMessage(
        message=ToolMessage(
            name=name,
            tool_call_id="call_123",
            content=[TextChunk(text=text)] if text is not None else None,
        ),
        tool_call_summary=tool_call_summary,
    )


def make_framework_message(
    content: str = "Framework content",
    summary: str | None = None,
    name: str = "Framework",
) -> FrameworkConversationMessage:
    return FrameworkConversationMessage(
        content=content,
        summary=summary,
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
# _wrap_think_block
# ---------------------------------------------------------------------------


class TestWrapThinkBlock:
    def test_wraps_text_in_thinking_block(self):
        result = _wrap_think_block("my thoughts")
        assert result == "```thinking\nmy thoughts\n```"

    def test_empty_string(self):
        result = _wrap_think_block("")
        assert result == "```thinking\n\n```"

    def test_multiline_text(self):
        result = _wrap_think_block("line 1\nline 2")
        assert result == "```thinking\nline 1\nline 2\n```"


# ---------------------------------------------------------------------------
# _render_assistant_chunk
# ---------------------------------------------------------------------------


class TestRenderAssistantChunk:
    def test_text_chunk_returns_text(self):
        chunk = TextChunk(text="Hello world")
        assert _render_assistant_chunk(chunk) == "Hello world"

    def test_think_chunk_wraps_in_thinking_block(self):
        chunk = ThinkChunk(thinking=[TextChunk(text="Let me think...")])
        result = _render_assistant_chunk(chunk)
        assert result == "```thinking\nLet me think...\n```"

    def test_think_chunk_with_multiple_text_chunks(self):
        chunk = ThinkChunk(
            thinking=[
                TextChunk(text="First thought. "),
                TextChunk(text="Second thought."),
            ]
        )
        result = _render_assistant_chunk(chunk)
        assert result == "```thinking\nFirst thought. Second thought.\n```"

    def test_think_chunk_with_empty_thinking(self):
        chunk = ThinkChunk(thinking=[])
        result = _render_assistant_chunk(chunk)
        assert result == "```thinking\n\n```"


# ---------------------------------------------------------------------------
# _render_tool_call
# ---------------------------------------------------------------------------


class TestRenderToolCall:
    def test_renders_tool_call_with_parameters(self):
        tool_call = make_tool_call(
            name="get_weather",
            arguments={"city": "Berlin", "units": "celsius"},
        )
        result = _render_tool_call(tool_call, condensed=False)
        assert result == (
            "### Tool Call: get_weather"
            "- city: Berlin"
            "- units: celsius"
        )

    def test_renders_tool_call_with_no_parameters(self):
        tool_call = make_tool_call(name="noop", arguments={})
        result = _render_tool_call(tool_call, condensed=False)
        assert result == "### Tool Call: noop"

    def test_condensed_truncates_parameter_values(self):
        tool_call = make_tool_call(
            name="search",
            arguments={"query": "very long search query"},
        )
        result = _render_tool_call(tool_call, condensed=True)
        assert result == (
            "### Tool Call: search"
            "- query: <parameter value truncated>"
        )

    def test_condensed_with_no_parameters(self):
        tool_call = make_tool_call(name="noop", arguments={})
        result = _render_tool_call(tool_call, condensed=True)
        assert result == "### Tool Call: noop"


# ---------------------------------------------------------------------------
# MarkdownRenderer - render_user_message
# ---------------------------------------------------------------------------


class TestRenderUserMessage:
    def test_renders_simple_user_message(self):
        renderer = MarkdownRenderer()
        msg = make_user_message("Hello world")
        result = renderer.render_user_message(msg)
        assert result == "## user (User):\nHello world"

    def test_renders_user_message_with_custom_name(self):
        renderer = MarkdownRenderer()
        msg = make_user_message("Hi")
        msg.name = "Alice"
        result = renderer.render_user_message(msg)
        assert result == "## Alice (User):\nHi"

    def test_ignores_non_text_chunks(self):
        renderer = MarkdownRenderer()
        msg = UserConversationMessage(
            message=UserMessage(
                content=[
                    TextChunk(text="Part 1"),
                    ThinkChunk(thinking=[TextChunk(text="should be ignored")]),
                    TextChunk(text="Part 2"),
                ]
            ),
            name="user",
        )
        result = renderer.render_user_message(msg)
        assert result == "## user (User):\nPart 1Part 2"

    def test_empty_content(self):
        renderer = MarkdownRenderer()
        msg = UserConversationMessage(
            message=UserMessage(content=None),
            name="user",
        )
        result = renderer.render_user_message(msg)
        assert result == "## user (User):\n"


# ---------------------------------------------------------------------------
# MarkdownRenderer - render_assistant_message
# ---------------------------------------------------------------------------


class TestRenderAssistantMessage:
    def test_renders_simple_assistant_message(self):
        renderer = MarkdownRenderer()
        msg = make_assistant_message("Hello!")
        result = renderer.render_assistant_message(msg)
        assert result == "## assistant (Assistant):\nHello!"

    def test_renders_assistant_message_with_custom_name(self):
        renderer = MarkdownRenderer()
        msg = make_assistant_message("Hi", name="Bot")
        result = renderer.render_assistant_message(msg)
        assert result == "## Bot (Assistant):\nHi"

    def test_renders_think_chunks_in_normal_mode(self):
        renderer = MarkdownRenderer()
        msg = AssistantConversationMessage(
            message=AssistantMessage(
                content=[
                    ThinkChunk(thinking=[TextChunk(text="Thinking...")]),
                    TextChunk(text="Here is my answer"),
                ]
            ),
            name="assistant",
        )
        result = renderer.render_assistant_message(msg)
        assert result == (
            "## assistant (Assistant):\n"
            "```thinking\nThinking...\n```"
            "Here is my answer"
        )

    def test_renders_tool_calls(self):
        renderer = MarkdownRenderer()
        msg = make_assistant_message(
            "Let me check...",
            tool_calls=[
                make_tool_call("get_weather", {"city": "Berlin"}),
            ],
        )
        result = renderer.render_assistant_message(msg)
        assert result == (
            "## assistant (Assistant):\n"
            "Let me check..."
            "### Tool Call: get_weather"
            "- city: Berlin"
        )

    def test_renders_multiple_tool_calls(self):
        renderer = MarkdownRenderer()
        msg = make_assistant_message(
            "Making calls...",
            tool_calls=[
                make_tool_call("search", {"q": "test"}, call_id="call_1"),
                make_tool_call("noop", {}, call_id="call_2"),
            ],
        )
        result = renderer.render_assistant_message(msg)
        assert result == (
            "## assistant (Assistant):\n"
            "Making calls..."
            "### Tool Call: search"
            "- q: test"
            "### Tool Call: noop"
        )

    def test_condensed_mode_uses_condensed_thoughts(self):
        renderer = MarkdownRenderer(condensed=True)
        msg = make_assistant_message(
            "My answer",
            condensed_thoughts="Condensed thinking",
        )
        result = renderer.render_assistant_message(msg)
        assert result == (
            "## assistant (Assistant):\n"
            "```thinking\nCondensed thinking\n```"
            "My answer"
        )

    def test_condensed_mode_ignores_think_chunks(self):
        """In condensed mode, ThinkChunks in content should be ignored."""
        renderer = MarkdownRenderer(condensed=True)
        msg = AssistantConversationMessage(
            message=AssistantMessage(
                content=[
                    ThinkChunk(thinking=[TextChunk(text="Original thoughts")]),
                    TextChunk(text="Answer"),
                ]
            ),
            name="assistant",
            condensed_thoughts="Condensed thoughts",
        )
        result = renderer.render_assistant_message(msg)
        assert result == (
            "## assistant (Assistant):\n"
            "```thinking\nCondensed thoughts\n```"
            "Answer"
        )

    def test_condensed_mode_without_condensed_thoughts_falls_back(self):
        """If condensed but no condensed_thoughts, fall back to normal rendering."""
        renderer = MarkdownRenderer(condensed=True)
        msg = AssistantConversationMessage(
            message=AssistantMessage(
                content=[
                    ThinkChunk(thinking=[TextChunk(text="Thinking...")]),
                    TextChunk(text="Answer"),
                ]
            ),
            name="assistant",
            condensed_thoughts=None,
        )
        result = renderer.render_assistant_message(msg)
        assert result == (
            "## assistant (Assistant):\n"
            "```thinking\nThinking...\n```"
            "Answer"
        )

    def test_condensed_mode_truncates_tool_call_parameters(self):
        renderer = MarkdownRenderer(condensed=True)
        msg = make_assistant_message(
            "Checking...",
            tool_calls=[
                make_tool_call("get_weather", {"city": "Berlin"}),
            ],
        )
        result = renderer.render_assistant_message(msg)
        assert result == (
            "## assistant (Assistant):\n"
            "Checking..."
            "### Tool Call: get_weather"
            "- city: <parameter value truncated>"
        )

    def test_empty_content(self):
        renderer = MarkdownRenderer()
        msg = make_assistant_message(None)
        result = renderer.render_assistant_message(msg)
        assert result == "## assistant (Assistant):\n"

    def test_empty_content_with_tool_calls(self):
        renderer = MarkdownRenderer()
        msg = make_assistant_message(
            None,
            tool_calls=[make_tool_call("noop", {})],
        )
        result = renderer.render_assistant_message(msg)
        assert result == "## assistant (Assistant):\n### Tool Call: noop"


# ---------------------------------------------------------------------------
# MarkdownRenderer - render_tool_message
# ---------------------------------------------------------------------------


class TestRenderToolMessage:
    def test_renders_simple_tool_message(self):
        renderer = MarkdownRenderer()
        msg = make_tool_message("Sunny, 22°C")
        result = renderer.render_tool_message(msg)
        assert result == "## get_weather (Tool):\nSunny, 22°C"

    def test_renders_tool_message_with_custom_name(self):
        renderer = MarkdownRenderer()
        msg = make_tool_message("result", name="custom_tool")
        result = renderer.render_tool_message(msg)
        assert result == "## custom_tool (Tool):\nresult"

    def test_ignores_non_text_chunks(self):
        renderer = MarkdownRenderer()
        msg = ToolConversationMessage(
            message=ToolMessage(
                name="tool",
                content=[
                    TextChunk(text="Result: "),
                    ThinkChunk(thinking=[TextChunk(text="ignored")]),
                    TextChunk(text="success"),
                ],
            ),
        )
        result = renderer.render_tool_message(msg)
        assert result == "## tool (Tool):\nResult: success"

    def test_condensed_mode_uses_tool_call_summary(self):
        renderer = MarkdownRenderer(condensed=True)
        msg = make_tool_message(
            "Full tool output here",
            tool_call_summary="Weather in Berlin: sunny",
        )
        result = renderer.render_tool_message(msg)
        assert result == "## get_weather (Tool):\nWeather in Berlin: sunny"

    def test_condensed_mode_without_summary_shows_truncated(self):
        renderer = MarkdownRenderer(condensed=True)
        msg = make_tool_message("Full output", tool_call_summary=None)
        result = renderer.render_tool_message(msg)
        assert result == "## get_weather (Tool):\n<tool output truncated>"

    def test_empty_content(self):
        renderer = MarkdownRenderer()
        msg = make_tool_message(None)
        result = renderer.render_tool_message(msg)
        assert result == "## get_weather (Tool):\n"


# ---------------------------------------------------------------------------
# MarkdownRenderer - render_framework_message
# ---------------------------------------------------------------------------


class TestRenderFrameworkMessage:
    def test_renders_simple_framework_message(self):
        renderer = MarkdownRenderer()
        msg = make_framework_message("Some framework message")
        result = renderer.render_framework_message(msg)
        assert result == "## Framework (Framework):\nSome framework message"

    def test_renders_framework_message_with_custom_name(self):
        renderer = MarkdownRenderer()
        msg = make_framework_message("content", name="System")
        result = renderer.render_framework_message(msg)
        assert result == "## System (Framework):\ncontent"

    def test_condensed_mode_uses_summary(self):
        renderer = MarkdownRenderer(condensed=True)
        msg = make_framework_message(
            "Full framework content",
            summary="Brief summary",
        )
        result = renderer.render_framework_message(msg)
        assert result == "## Framework (Framework):\nBrief summary"

    def test_condensed_mode_without_summary_shows_unavailable(self):
        renderer = MarkdownRenderer(condensed=True)
        msg = make_framework_message("content", summary=None)
        result = renderer.render_framework_message(msg)
        assert result == (
            "## Framework (Framework):\n<framework message content unavailable>"
        )


# ---------------------------------------------------------------------------
# MarkdownRenderer - render_message (dispatcher)
# ---------------------------------------------------------------------------


class TestRenderMessage:
    def test_dispatches_user_message(self):
        renderer = MarkdownRenderer()
        msg = make_user_message("Hello")
        result = renderer.render_message(msg)
        assert result == "## user (User):\nHello"

    def test_dispatches_assistant_message(self):
        renderer = MarkdownRenderer()
        msg = make_assistant_message("Hi")
        result = renderer.render_message(msg)
        assert result == "## assistant (Assistant):\nHi"

    def test_dispatches_tool_message(self):
        renderer = MarkdownRenderer()
        msg = make_tool_message("result")
        result = renderer.render_message(msg)
        assert result == "## get_weather (Tool):\nresult"

    def test_dispatches_framework_message(self):
        renderer = MarkdownRenderer()
        msg = make_framework_message("content")
        result = renderer.render_message(msg)
        assert result == "## Framework (Framework):\ncontent"


# ---------------------------------------------------------------------------
# MarkdownRenderer - render_turn
# ---------------------------------------------------------------------------


class TestRenderTurn:
    def test_renders_turn_with_user_and_assistant(self):
        renderer = MarkdownRenderer()
        turn = Turn(
            user_message=make_user_message("Hello"),
            assistant_response=make_assistant_message("Hi there"),
            usage=make_usage(),
        )
        result = renderer.render_turn(turn)
        assert result == (
            "## user (User):\nHello"
            "## assistant (Assistant):\nHi there"
        )

    def test_renders_turn_with_tool_messages(self):
        renderer = MarkdownRenderer()
        turn = Turn(
            tool_messages=[
                make_tool_message("Tool result", name="search"),
            ],
            assistant_response=make_assistant_message("Based on results..."),
            usage=make_usage(),
        )
        result = renderer.render_turn(turn)
        assert result == (
            "## search (Tool):\nTool result"
            "## assistant (Assistant):\nBased on results..."
        )

    def test_renders_turn_with_multiple_tool_messages(self):
        renderer = MarkdownRenderer()
        turn = Turn(
            tool_messages=[
                make_tool_message("Result 1", name="tool_a"),
                make_tool_message("Result 2", name="tool_b"),
            ],
            assistant_response=make_assistant_message("Done"),
            usage=make_usage(),
        )
        result = renderer.render_turn(turn)
        assert result == (
            "## tool_a (Tool):\nResult 1"
            "## tool_b (Tool):\nResult 2"
            "## assistant (Assistant):\nDone"
        )


# ---------------------------------------------------------------------------
# MarkdownRenderer - integration / combined scenarios
# ---------------------------------------------------------------------------


class TestMarkdownRendererIntegration:
    def test_full_conversation_flow(self):
        """Test a complete conversation with user, assistant with thinking, and tool calls."""
        renderer = MarkdownRenderer()

        user_msg = make_user_message("What's the weather in Berlin?")
        assert renderer.render_message(user_msg) == (
            "## user (User):\nWhat's the weather in Berlin?"
        )

        assistant_msg = AssistantConversationMessage(
            message=AssistantMessage(
                content=[
                    ThinkChunk(thinking=[TextChunk(text="I need to check the weather")]),
                    TextChunk(text="Let me look that up for you."),
                ],
                tool_calls=[
                    make_tool_call("get_weather", {"city": "Berlin"}),
                ],
            ),
            name="assistant",
        )
        assert renderer.render_message(assistant_msg) == (
            "## assistant (Assistant):\n"
            "```thinking\nI need to check the weather\n```"
            "Let me look that up for you."
            "### Tool Call: get_weather"
            "- city: Berlin"
        )

        tool_msg = make_tool_message("Sunny, 22°C, clear skies")
        assert renderer.render_message(tool_msg) == (
            "## get_weather (Tool):\nSunny, 22°C, clear skies"
        )

        final_msg = make_assistant_message("It's sunny and 22°C in Berlin!")
        assert renderer.render_message(final_msg) == (
            "## assistant (Assistant):\nIt's sunny and 22°C in Berlin!"
        )

    def test_condensed_full_flow(self):
        """Test condensed mode across all message types."""
        renderer = MarkdownRenderer(condensed=True)

        assistant_msg = make_assistant_message(
            "Answer",
            condensed_thoughts="Brief thought",
            tool_calls=[
                make_tool_call("search", {"query": "secret query"}),
            ],
        )
        assert renderer.render_message(assistant_msg) == (
            "## assistant (Assistant):\n"
            "```thinking\nBrief thought\n```"
            "Answer"
            "### Tool Call: search"
            "- query: <parameter value truncated>"
        )

        tool_msg = make_tool_message(
            "Full output",
            tool_call_summary="Brief output",
        )
        assert renderer.render_message(tool_msg) == (
            "## get_weather (Tool):\nBrief output"
        )

        framework_msg = make_framework_message(
            "Full content",
            summary="Brief content",
        )
        assert renderer.render_message(framework_msg) == (
            "## Framework (Framework):\nBrief content"
        )

    def test_default_is_not_condensed(self):
        """Default renderer should not be in condensed mode."""
        renderer = MarkdownRenderer()
        assert renderer._condensed is False

    def test_condensed_parameter(self):
        """Condensed parameter should be stored correctly."""
        renderer = MarkdownRenderer(condensed=True)
        assert renderer._condensed is True
