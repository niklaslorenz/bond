"""Tests for bond.providers.general.util.tool_loop_runner module."""

from typing import Any
from unittest.mock import MagicMock, patch

from bond.capabilities.types import MessageListBuilder, SystemMessageBuilder
from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    Message,
    SystemMessage,
    TextChunk,
    ToolCall,
    Turn,
    UsageInfo,
    UserConversationMessage,
    UserMessage,
)
from bond.endpoints.chat_completions import (
    CompletionChoice,
    CompletionResponse,
)
from bond.providers.general.util.tool_loop_runner import (
    ToolLoopRunner,
    ToolLoopRunnerOptions,
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
    name: str = "assistant",
) -> AssistantConversationMessage:
    return AssistantConversationMessage(
        message=AssistantMessage(content=[TextChunk(text=text)]),
        name=name,
    )


def make_turn(
    user_text: str = "Hello",
    assistant_text: str = "Hi",
) -> Turn:
    return Turn(
        user_message=make_user_message(user_text),
        assistant_response=make_assistant_message(assistant_text),
        usage=make_usage(),
    )


def make_conversation(*turns: Turn) -> Conversation:
    """Create a conversation with the given turns in the last episode."""
    conv = Conversation()
    for turn in turns:
        conv.add_turn(turn)
    return conv


def make_completion_response(
    text: str | None = "Response",
    tool_calls: list[ToolCall] | None = None,
) -> CompletionResponse:
    """Create a CompletionResponse for testing."""
    return CompletionResponse(
        choices=[
            CompletionChoice(
                finish_reason="stop",  # type: ignore[arg-type]
                message=AssistantMessage(
                    content=[TextChunk(text=text)] if text is not None else None,
                    tool_calls=tool_calls,
                ),
            )
        ],
        created=1234567890,
        id="chatcmpl-test",
        model="test-model",
        usage=make_usage(),
    )


class MockChatCompletionsEndpoint:
    """A mock ChatCompletionsEndpoint for testing."""

    def __init__(self, responses: list[CompletionResponse] | None = None):
        self._responses = responses or []
        self._call_count = 0
        self.calls: list[dict] = []

    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list,
        system_message: SystemMessage | None = None,
        options: dict[str, Any] | None = None,
        max_retries: int = 10,
    ) -> CompletionResponse:
        self.calls.append(
            {
                "model": model,
                "messages": list(messages),  # Copy to capture state
                "tools": tools,
                "system_message": system_message,
                "options": options,
                "max_retries": max_retries,
            }
        )
        if self._call_count < len(self._responses):
            response = self._responses[self._call_count]
        else:
            response = make_completion_response(text="Done")
        self._call_count += 1
        return response

    def stream_chat_completion(self, *args, **kwargs):
        raise NotImplementedError

    def supports_streaming(self) -> bool:
        return False


class MockSystemMessageBuilder(SystemMessageBuilder):
    """A mock SystemMessageBuilder for testing."""

    def __init__(self, return_value: SystemMessage | None = None):
        self._return_value = return_value or SystemMessage.create("System prompt")
        self.calls: list[dict] = []

    def render_system_message(
        self,
        conversation: Conversation,
        prompt: str | None,
    ) -> SystemMessage | None:
        self.calls.append({"conversation": conversation, "prompt": prompt})
        return self._return_value


class MockMessageListBuilder(MessageListBuilder):
    """A mock MessageListBuilder for testing."""

    def __init__(self, return_value: list[Message] | None = None):
        super().__init__(lambda x: sum(x, []))
        self._return_value = return_value or []
        self.calls: list[dict] = []

    def render_user_message(self, user_message) -> list[Message]:
        return [user_message.message]

    def render_assistant_message(self, assistant_message) -> list[Message]:
        return [assistant_message.message]

    def render_tool_message(self, tool_message) -> list[Message]:
        return [tool_message.message]

    def render_framework_message(self, framework_message) -> list[Message]:
        return []

    def render_conversation(
        self, conversation: Conversation, turns: int | slice | None = None
    ) -> list[Message]:
        self.calls.append({"conversation": conversation, "turns": turns})
        return list(self._return_value)  # Return a copy


# ---------------------------------------------------------------------------
# ToolLoopRunnerOptions
# ---------------------------------------------------------------------------


class TestToolLoopRunnerOptions:
    def test_creation_with_required_fields(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="You are helpful",
            instruction="Do something",
            iterations=5,
        )
        assert options.model == "test-model"
        assert options.prompt == "You are helpful"
        assert options.instruction == "Do something"
        assert options.iterations == 5
        assert options.model_options is None

    def test_creation_with_model_options(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            model_options={"temperature": 0.5},
            prompt="You are helpful",
            instruction="Do something",
            iterations=5,
        )
        assert options.model_options == {"temperature": 0.5}

    def test_resolve_without_runtime(self):
        """Test resolve() with no runtime - should just return the strings unchanged."""
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="You are helpful",
            instruction="Do something",
            iterations=5,
        )
        # resolve(None) will try to get BondRuntime.get_instance() which may fail
        # We'll test this with a mock runtime instead
        options.prompt = "Hello {SKILL:test}"
        options.instruction = "Do {SKILL:thing}"

        mock_runtime = MagicMock()
        mock_runtime.get_skill = lambda name: f"<skill:{name}>"

        options.resolve(mock_runtime)

        assert options.prompt == "Hello <skill:test>"
        assert options.instruction == "Do <skill:thing>"

    def test_resolve_with_no_skills(self):
        """Test resolve() with strings that don't contain skill patterns."""
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="You are helpful",
            instruction="Do something",
            iterations=5,
        )

        mock_runtime = MagicMock()
        options.resolve(mock_runtime)

        assert options.prompt == "You are helpful"
        assert options.instruction == "Do something"
        mock_runtime.get_skill.assert_not_called()


# ---------------------------------------------------------------------------
# ToolLoopRunner - initialization
# ---------------------------------------------------------------------------


class TestToolLoopRunnerInit:
    def test_stores_options(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="prompt",
            instruction="instruction",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint()
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        with patch(
            "bond.providers.general.util.tool_loop_runner.ToolCallLoop"
        ) as mock_loop_class:
            runner = ToolLoopRunner(
                options, endpoint, system_builder, message_builder, runtime=None
            )
            assert runner._options is options

    def test_creates_toolbox_with_task_list_toolset(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="prompt",
            instruction="instruction",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint()
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )

        # The toolbox should have the task_list tools
        tool_names = [t.function.name for t in runner._toolbox.tool_descriptions]
        assert "add_tasks" in tool_names
        assert "complete_tasks" in tool_names
        assert "delete_tasks" in tool_names
        assert "clear_tasks" in tool_names
        assert "clear_completed_tasks" in tool_names

    def test_creates_tool_call_loop(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="prompt",
            instruction="instruction",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint()
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )

        assert runner._tool_call_loop is not None
        assert runner._tool_call_loop._toolbox is runner._toolbox
        assert runner._tool_call_loop._chat_completions is endpoint


# ---------------------------------------------------------------------------
# ToolLoopRunner - run
# ---------------------------------------------------------------------------


class TestToolLoopRunnerRun:
    def test_calls_system_message_builder(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="You are helpful",
            instruction="Do something",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation(make_turn("Hello", "Hi"))
        runner.run(conv, turns=None)

        assert len(system_builder.calls) == 1
        assert system_builder.calls[0]["conversation"] is conv
        assert system_builder.calls[0]["prompt"] == "You are helpful"

    def test_calls_message_list_builder(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="You are helpful",
            instruction="Do something",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation(make_turn("Hello", "Hi"))
        runner.run(conv, turns=2)

        assert len(message_builder.calls) == 1
        assert message_builder.calls[0]["conversation"] is conv
        assert message_builder.calls[0]["turns"] == 2

    def test_appends_instruction_as_user_message(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="You are helpful",
            instruction="Do something important",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder(return_value=[])

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation()
        runner.run(conv, turns=None)

        # Check that the endpoint was called with the instruction as the last message
        assert len(endpoint.calls) == 1
        messages = endpoint.calls[0]["messages"]
        assert len(messages) == 1
        assert isinstance(messages[0], UserMessage)
        assert messages[0].content[0].text == "Do something important"

    def test_passes_model_and_options_to_tool_call_loop(self):
        options = ToolLoopRunnerOptions(
            model="my-model",
            model_options={"temperature": 0.7},
            prompt="You are helpful",
            instruction="Do something",
            iterations=3,
        )
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation()
        runner.run(conv, turns=None)

        call = endpoint.calls[0]
        assert call["model"] == "my-model"
        assert call["options"] == {"temperature": 0.7}

    def test_passes_iterations_to_tool_call_loop(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="prompt",
            instruction="instruction",
            iterations=7,
        )
        # Create enough responses for 7 iterations
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text=f"Response {i}") for i in range(10)]
        )
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation()
        runner.run(conv, turns=None)

        # With no tool calls, should only make 1 call
        assert endpoint._call_count == 1

    def test_uses_default_model_options_when_none(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            model_options=None,
            prompt="prompt",
            instruction="instruction",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation()
        runner.run(conv, turns=None)

        assert endpoint.calls[0]["options"] == {}

    def test_creates_tool_call_context_with_conversation(self):
        """Test that the ToolCallContext is created with the conversation."""
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="prompt",
            instruction="instruction",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation(make_turn("Hello", "Hi"))
        runner.run(conv, turns=None)

        # The tool_call_loop.run was called, which means the context was created
        # We can verify by checking that the endpoint was called (which means the loop ran)
        assert len(endpoint.calls) == 1

    def test_includes_existing_messages_from_builder(self):
        """Test that messages from the message list builder are included."""
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="prompt",
            instruction="instruction",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        system_builder = MockSystemMessageBuilder()
        existing_messages: list[Message] = [
            UserMessage.create("Previous message 1"),
            AssistantMessage(content=[TextChunk(text="Previous response")]),
        ]
        message_builder = MockMessageListBuilder(return_value=existing_messages)

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation()
        runner.run(conv, turns=None)

        messages = endpoint.calls[0]["messages"]
        # Should have: 2 existing messages + 1 instruction message
        assert len(messages) == 3
        assert isinstance(messages[0], UserMessage)
        assert messages[0].content[0].text == "Previous message 1"
        assert isinstance(messages[1], AssistantMessage)
        assert isinstance(messages[2], UserMessage)
        assert messages[2].content[0].text == "instruction"

    def test_system_message_passed_to_endpoint(self):
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="You are a helpful assistant",
            instruction="instruction",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        custom_system_msg = SystemMessage.create("Custom system prompt")
        system_builder = MockSystemMessageBuilder(return_value=custom_system_msg)
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation()
        runner.run(conv, turns=None)

        assert endpoint.calls[0]["system_message"] is custom_system_msg


# ---------------------------------------------------------------------------
# ToolLoopRunner - integration with real ToolCallLoop
# ---------------------------------------------------------------------------


class TestToolLoopRunnerIntegration:
    def test_full_run_with_task_list_tool(self):
        """Test a full run where the model calls a task list tool."""
        from bond.conversation.types import FunctionCall, ToolCall

        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="You are helpful",
            instruction="Add a task",
            iterations=5,
        )

        # Create a tool call for add_tasks
        tool_call = ToolCall(
            id="call_1",
            function=FunctionCall(name="add_tasks", arguments={"tasks": ["Test task"]}),
        )
        endpoint = MockChatCompletionsEndpoint(
            responses=[
                make_completion_response(
                    text=None, tool_calls=[tool_call]
                ),
                make_completion_response(text="Task added!"),
            ]
        )
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation()
        runner.run(conv, turns=None)

        # Should have made 2 calls: one with tool call, one final response
        assert endpoint._call_count == 2

        # The task should have been added to the conversation's task list
        assert conv.task_list is not None
        assert len(conv.task_list) == 1
        assert conv.task_list.content[0].description == "Test task"

    def test_run_with_turns_limit(self):
        """Test that the turns limit is passed to the message list builder."""
        options = ToolLoopRunnerOptions(
            model="test-model",
            prompt="prompt",
            instruction="instruction",
            iterations=5,
        )
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        system_builder = MockSystemMessageBuilder()
        message_builder = MockMessageListBuilder()

        runner = ToolLoopRunner(
            options, endpoint, system_builder, message_builder, runtime=None
        )
        conv = make_conversation(
            make_turn("First", "Response 1"),
            make_turn("Second", "Response 2"),
        )
        runner.run(conv, turns=1)

        assert message_builder.calls[0]["turns"] == 1
