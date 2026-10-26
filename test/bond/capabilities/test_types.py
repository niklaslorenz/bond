"""Tests for bond.capabilities.types module."""

from typing import Iterable

import pytest

from bond.capabilities.types import (
    ConversationRenderer,
    MessageListBuilder,
    SystemMessageBuilder,
)
from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    Message,
    SystemMessage,
    TextChunk,
    ToolConversationMessage,
    ToolMessage,
    Turn,
    UsageInfo,
    UserConversationMessage,
    UserMessage,
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


def make_user_conversation_message(
    text: str = "Hello",
    name: str = "user",
) -> UserConversationMessage:
    return UserConversationMessage(
        message=UserMessage.create(text),
        name=name,
    )


def make_assistant_conversation_message(
    text: str = "Hi there",
    name: str = "assistant",
) -> AssistantConversationMessage:
    return AssistantConversationMessage(
        message=AssistantMessage(content=[TextChunk(text=text)]),
        name=name,
    )


def make_tool_conversation_message(
    name: str = "get_weather",
    tool_call_id: str = "call_123",
    content: str = '{"temp": 22}',
) -> ToolConversationMessage:
    return ToolConversationMessage(
        message=ToolMessage(
            name=name,
            tool_call_id=tool_call_id,
            content=[TextChunk(text=content)],
        ),
    )


def make_turn(
    user_text: str = "Hello",
    assistant_text: str = "Hi there",
) -> Turn:
    return Turn(
        user_message=make_user_conversation_message(user_text),
        assistant_response=make_assistant_conversation_message(assistant_text),
        usage=make_usage(),
    )


def make_tool_turn(
    tool_name: str = "search",
    tool_call_id: str = "call_1",
    tool_result: str = "result",
    assistant_text: str = "Based on results...",
) -> Turn:
    return Turn(
        tool_messages=[
            make_tool_conversation_message(
                name=tool_name,
                tool_call_id=tool_call_id,
                content=tool_result,
            )
        ],
        assistant_response=make_assistant_conversation_message(assistant_text),
        usage=make_usage(),
    )


def make_conversation(*turns: Turn) -> Conversation:
    """Create a conversation with the given turns in the last episode."""
    conv = Conversation()
    for turn in turns:
        conv.add_turn(turn)
    return conv


class StringRenderer(ConversationRenderer[str]):
    """A simple renderer that joins message texts with newlines."""

    def render_user_message(self, user_message: UserConversationMessage) -> str:
        chunks = user_message.message.content or []
        texts = [c.text for c in chunks if isinstance(c, TextChunk)]
        return f"User: {' '.join(texts)}"

    def render_assistant_message(
        self, assistant_message: AssistantConversationMessage
    ) -> str:
        chunks = assistant_message.message.content or []
        texts = [c.text for c in chunks if isinstance(c, TextChunk)]
        return f"Assistant: {' '.join(texts)}"

    def render_tool_message(self, tool_message: ToolConversationMessage) -> str:
        chunks = tool_message.message.content or []
        texts = [c.text for c in chunks if isinstance(c, TextChunk)]
        return f"Tool({tool_message.name}): {' '.join(texts)}"


class ListRenderer(ConversationRenderer[list[Message]]):
    """A renderer that converts messages to a list of Message objects."""

    def render_user_message(
        self, user_message: UserConversationMessage
    ) -> list[Message]:
        return [user_message.message]

    def render_assistant_message(
        self, assistant_message: AssistantConversationMessage
    ) -> list[Message]:
        return [assistant_message.message]

    def render_tool_message(
        self, tool_message: ToolConversationMessage
    ) -> list[Message]:
        return [tool_message.message]


def join_strings(items: Iterable[str]) -> str:
    """Compose function for StringRenderer: join with newlines."""
    return "\n".join(items)


def concat_lists(items: Iterable[list[Message]]) -> list[Message]:
    """Compose function for ListRenderer: concatenate lists."""
    result: list[Message] = []
    for lst in items:
        result.extend(lst)
    return result


# ---------------------------------------------------------------------------
# ConversationRenderer - abstract behavior
# ---------------------------------------------------------------------------


class TestConversationRendererAbstract:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            ConversationRenderer(join_strings)  # pyright: ignore[reportAbstractUsage]

    def test_subclass_must_implement_all_abstract_methods(self):
        """A subclass missing abstract methods cannot be instantiated."""

        class IncompleteRenderer(ConversationRenderer[str]):
            def render_user_message(
                self, user_message: UserConversationMessage
            ) -> str:
                return "user"

            # Missing render_assistant_message and render_tool_message

        with pytest.raises(TypeError):
            IncompleteRenderer(join_strings)  # pyright: ignore[reportAbstractUsage]

    def test_subclass_with_only_two_methods_cannot_instantiate(self):
        """Even with two of three methods, instantiation should fail."""

        class PartialRenderer(ConversationRenderer[str]):
            def render_user_message(
                self, user_message: UserConversationMessage
            ) -> str:
                return "user"

            def render_assistant_message(
                self, assistant_message: AssistantConversationMessage
            ) -> str:
                return "assistant"

            # Missing render_tool_message

        with pytest.raises(TypeError):
            PartialRenderer(join_strings)  # pyright: ignore[reportAbstractUsage]


# ---------------------------------------------------------------------------
# ConversationRenderer - initialization
# ---------------------------------------------------------------------------


class TestConversationRendererInit:
    def test_compose_function_stored(self):
        renderer = StringRenderer(join_strings)
        assert renderer._compose is join_strings

    def test_custom_compose_function(self):
        def custom_compose(items: Iterable[str]) -> str:
            return " | ".join(items)

        renderer = StringRenderer(custom_compose)
        assert renderer._compose is custom_compose


# ---------------------------------------------------------------------------
# ConversationRenderer - render_message dispatch
# ---------------------------------------------------------------------------


class TestRenderMessage:
    def test_render_user_message(self):
        renderer = StringRenderer(join_strings)
        msg = make_user_conversation_message("Hello world")
        result = renderer.render_message(msg)
        assert result == "User: Hello world"

    def test_render_assistant_message(self):
        renderer = StringRenderer(join_strings)
        msg = make_assistant_conversation_message("Hi there")
        result = renderer.render_message(msg)
        assert result == "Assistant: Hi there"

    def test_render_tool_message(self):
        renderer = StringRenderer(join_strings)
        msg = make_tool_conversation_message(name="get_weather", content="sunny")
        result = renderer.render_message(msg)
        assert result == "Tool(get_weather): sunny"

    def test_render_message_returns_correct_type(self):
        """The return type should match the generic parameter T."""
        renderer = StringRenderer(join_strings)
        msg = make_user_conversation_message("test")
        result = renderer.render_message(msg)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# ConversationRenderer - render_turn
# ---------------------------------------------------------------------------


class TestRenderTurn:
    def test_render_user_triggered_turn(self):
        renderer = StringRenderer(join_strings)
        turn = make_turn(user_text="Hello", assistant_text="Hi")
        result = renderer.render_turn(turn)
        assert result == "User: Hello\nAssistant: Hi"

    def test_render_tool_triggered_turn(self):
        renderer = StringRenderer(join_strings)
        turn = make_tool_turn(
            tool_name="search",
            tool_result="found 5 items",
            assistant_text="Here are the results",
        )
        result = renderer.render_turn(turn)
        assert result == "Tool(search): found 5 items\nAssistant: Here are the results"

    def test_render_turn_with_multiple_tool_messages(self):
        renderer = StringRenderer(join_strings)
        turn = Turn(
            tool_messages=[
                make_tool_conversation_message(name="tool1", content="result1"),
                make_tool_conversation_message(name="tool2", content="result2"),
            ],
            assistant_response=make_assistant_conversation_message("Done"),
            usage=make_usage(),
        )
        result = renderer.render_turn(turn)
        assert "Tool(tool1): result1" in result
        assert "Tool(tool2): result2" in result
        assert "Assistant: Done" in result

    def test_render_turn_uses_compose_function(self):
        """The compose function should be called with all rendered messages."""

        def counting_compose(items: Iterable[str]) -> str:
            items_list = list(items)
            return f"COUNT:{len(items_list)}"

        renderer = StringRenderer(counting_compose)
        turn = make_turn()
        result = renderer.render_turn(turn)
        assert result == "COUNT:2"  # user + assistant


# ---------------------------------------------------------------------------
# ConversationRenderer - render_conversation
# ---------------------------------------------------------------------------


class TestRenderConversation:
    def test_render_conversation_single_turn(self):
        renderer = StringRenderer(join_strings)
        conv = make_conversation(make_turn("Hello", "Hi"))
        result = renderer.render_conversation(conv)
        assert result == "User: Hello\nAssistant: Hi"

    def test_render_conversation_multiple_turns(self):
        renderer = StringRenderer(join_strings)
        conv = make_conversation(
            make_turn("First", "Response 1"),
            make_turn("Second", "Response 2"),
        )
        result = renderer.render_conversation(conv)
        assert "User: First" in result
        assert "Assistant: Response 1" in result
        assert "User: Second" in result
        assert "Assistant: Response 2" in result

    def test_render_conversation_empty(self):
        """An empty conversation should produce an empty composition."""
        renderer = StringRenderer(join_strings)
        conv = Conversation()
        result = renderer.render_conversation(conv)
        assert result == ""

    def test_render_conversation_with_turns_limit(self):
        """Limiting to N turns renders the first N turns (slice(None, N))."""
        renderer = StringRenderer(join_strings)
        conv = make_conversation(
            make_turn("First", "Response 1"),
            make_turn("Second", "Response 2"),
            make_turn("Third", "Response 3"),
        )
        result = renderer.render_conversation(conv, turns=1)
        assert "User: First" in result
        assert "Assistant: Response 1" in result
        assert "Second" not in result
        assert "Third" not in result

    def test_render_conversation_with_turns_limit_2(self):
        """Limiting to 2 turns renders the first 2 turns."""
        renderer = StringRenderer(join_strings)
        conv = make_conversation(
            make_turn("First", "Response 1"),
            make_turn("Second", "Response 2"),
            make_turn("Third", "Response 3"),
        )
        result = renderer.render_conversation(conv, turns=2)
        assert "User: First" in result
        assert "User: Second" in result
        assert "Third" not in result

    def test_render_conversation_with_slice(self):
        """Using a slice should select a range of turns."""
        renderer = StringRenderer(join_strings)
        conv = make_conversation(
            make_turn("First", "Response 1"),
            make_turn("Second", "Response 2"),
            make_turn("Third", "Response 3"),
        )
        # Slice to get only the middle turn
        result = renderer.render_conversation(conv, turns=slice(1, 2))
        assert "First" not in result
        assert "User: Second" in result
        assert "Third" not in result

    def test_render_conversation_with_slice_all(self):
        """A full slice should include all turns."""
        renderer = StringRenderer(join_strings)
        conv = make_conversation(
            make_turn("First", "Response 1"),
            make_turn("Second", "Response 2"),
        )
        result = renderer.render_conversation(conv, turns=slice(None))
        assert "First" in result
        assert "Second" in result

    def test_render_conversation_with_none_turns(self):
        """None should include all turns (default behavior)."""
        renderer = StringRenderer(join_strings)
        conv = make_conversation(
            make_turn("First", "Response 1"),
            make_turn("Second", "Response 2"),
        )
        result = renderer.render_conversation(conv, turns=None)
        assert "First" in result
        assert "Second" in result

    def test_render_conversation_uses_compose(self):
        """The compose function should receive all rendered messages."""

        def counting_compose(items: Iterable[str]) -> str:
            items_list = list(items)
            return f"TOTAL:{len(items_list)}"

        renderer = StringRenderer(counting_compose)
        conv = make_conversation(
            make_turn("A", "B"),
            make_turn("C", "D"),
        )
        result = renderer.render_conversation(conv)
        assert result == "TOTAL:4"  # 2 turns × 2 messages each

    def test_render_conversation_with_tool_turns(self):
        """Tool-triggered turns should be rendered correctly."""
        renderer = StringRenderer(join_strings)
        conv = make_conversation(
            make_turn("What's the weather?", "Let me check"),
            make_tool_turn(
                tool_name="get_weather",
                tool_result='{"temp": 22}',
                assistant_text="It's 22 degrees",
            ),
        )
        result = renderer.render_conversation(conv)
        assert "User: What's the weather?" in result
        assert "Assistant: Let me check" in result
        assert "Tool(get_weather)" in result
        assert "Assistant: It's 22 degrees" in result


# ---------------------------------------------------------------------------
# ConversationRenderer with list type (MessageListBuilder pattern)
# ---------------------------------------------------------------------------


class TestListRenderer:
    def test_render_message_returns_list(self):
        renderer = ListRenderer(concat_lists)
        msg = make_user_conversation_message("Hello")
        result = renderer.render_message(msg)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], UserMessage)

    def test_render_turn_returns_flat_list(self):
        renderer = ListRenderer(concat_lists)
        turn = make_turn("Hello", "Hi")
        result = renderer.render_turn(turn)
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], UserMessage)
        assert isinstance(result[1], AssistantMessage)

    def test_render_conversation_returns_flat_list(self):
        renderer = ListRenderer(concat_lists)
        conv = make_conversation(
            make_turn("First", "Response 1"),
            make_turn("Second", "Response 2"),
        )
        result = renderer.render_conversation(conv)
        assert isinstance(result, list)
        assert len(result) == 4  # 2 turns × 2 messages
        assert isinstance(result[0], UserMessage)
        assert isinstance(result[1], AssistantMessage)
        assert isinstance(result[2], UserMessage)
        assert isinstance(result[3], AssistantMessage)

    def test_render_conversation_with_tool_message(self):
        renderer = ListRenderer(concat_lists)
        conv = make_conversation(
            make_turn("Check weather", "Looking up"),
            make_tool_turn(
                tool_name="get_weather",
                tool_result="sunny",
                assistant_text="It's sunny",
            ),
        )
        result = renderer.render_conversation(conv)
        assert len(result) == 4
        assert isinstance(result[2], ToolMessage)
        assert isinstance(result[3], AssistantMessage)


# ---------------------------------------------------------------------------
# SystemMessageBuilder - abstract behavior
# ---------------------------------------------------------------------------


class TestSystemMessageBuilderAbstract:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            SystemMessageBuilder()  # pyright: ignore[reportAbstractUsage]

    def test_subclass_must_implement_abstract_method(self):
        """A subclass without implementing render_system_message cannot instantiate."""

        class IncompleteBuilder(SystemMessageBuilder):
            pass

        with pytest.raises(TypeError):
            IncompleteBuilder()  # pyright: ignore[reportAbstractUsage]


# ---------------------------------------------------------------------------
# SystemMessageBuilder - concrete implementation
# ---------------------------------------------------------------------------


class SimpleSystemMessageBuilder(SystemMessageBuilder):
    """A simple builder that creates a system message from the prompt."""

    def render_system_message(
        self,
        conversation: Conversation,
        prompt: str | None,
    ) -> SystemMessage | None:
        if prompt is None:
            return None
        return SystemMessage.create(prompt)


class TestSystemMessageBuilderImplementation:
    def test_render_system_message_with_prompt(self):
        builder = SimpleSystemMessageBuilder()
        conv = Conversation()
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert isinstance(result, SystemMessage)
        assert result.role == "system"
        assert len(result.content) == 1
        assert isinstance(result.content[0], TextChunk)
        assert result.content[0].text == "You are helpful"

    def test_render_system_message_with_none_prompt(self):
        builder = SimpleSystemMessageBuilder()
        conv = Conversation()
        result = builder.render_system_message(conv, None)
        assert result is None

    def test_render_system_message_returns_system_message_type(self):
        builder = SimpleSystemMessageBuilder()
        conv = Conversation()
        result = builder.render_system_message(conv, "prompt")
        assert isinstance(result, SystemMessage)


# ---------------------------------------------------------------------------
# MessageListBuilder type alias
# ---------------------------------------------------------------------------


class TestMessageListBuilder:
    def test_type_alias_is_conversation_renderer_of_list_message(self):
        """MessageListBuilder should be ConversationRenderer[list[Message]]."""
        # The type alias is defined as ConversationRenderer[list[Message]]
        # We verify this by checking that a ListRenderer is compatible
        renderer = ListRenderer(concat_lists)
        assert isinstance(renderer, ConversationRenderer)

    def test_message_list_builder_can_be_subclassed(self):
        """Verify that the type alias can be used for subclassing."""

        class MyMessageListBuilder(MessageListBuilder):
            def render_user_message(
                self, user_message: UserConversationMessage
            ) -> list[Message]:
                return [user_message.message]

            def render_assistant_message(
                self, assistant_message: AssistantConversationMessage
            ) -> list[Message]:
                return [assistant_message.message]

            def render_tool_message(
                self, tool_message: ToolConversationMessage
            ) -> list[Message]:
                return [tool_message.message]

        builder = MyMessageListBuilder(concat_lists)
        turn = make_turn("Hello", "Hi")
        result = builder.render_turn(turn)
        assert len(result) == 2
        assert isinstance(result[0], UserMessage)
        assert isinstance(result[1], AssistantMessage)
