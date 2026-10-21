"""Tests for bond.providers.general.util.tool_loop_runner module."""

from typing import Any

from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantMessage,
    FunctionCall,
    Message,
    SystemMessage,
    TextChunk,
    ToolCall,
    UsageInfo,
    UserMessage,
)
from bond.endpoints.chat_completions import CompletionChoice, CompletionResponse
from bond.providers.general.util.default_message_list_builder import (
    DefaultMessageListBuilder,
)
from bond.providers.general.util.tool_loop_runner import (
    ToolLoopRunner,
    ToolLoopRunnerOptions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_usage(total_tokens: int = 30) -> UsageInfo:
    return UsageInfo(completion_tokens=10, prompt_tokens=20, total_tokens=total_tokens)


def make_conversation() -> Conversation:
    return Conversation()


def text_response(text: str) -> AssistantMessage:
    return AssistantMessage(content=[TextChunk(text=text)])


def tool_call_response(name: str, arguments: dict, call_id: str) -> AssistantMessage:
    return AssistantMessage(
        tool_calls=[
            ToolCall(id=call_id, function=FunctionCall(name=name, arguments=arguments))
        ]
    )


def message_text(msg) -> str:
    return "".join(
        chunk.text for chunk in (msg.content or []) if isinstance(chunk, TextChunk)
    )


class FakeChatCompletions:
    """Returns scripted responses in order and records every call."""

    def __init__(self, responses: list[AssistantMessage]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def chat_completion(
        self,
        model,
        messages,
        tools,
        system_message=None,
        options=None,
        max_retries=3,
    ):
        self.calls.append(
            {
                "model": model,
                "messages": list(messages),
                "tools": list(tools),
                "system_message": system_message,
                "options": options,
                "max_retries": max_retries,
            }
        )
        if not self.responses:
            raise RuntimeError("FakeChatCompletions: no scripted response left")
        message = self.responses.pop(0)
        return CompletionResponse(
            choices=[CompletionChoice(finish_reason="stop", message=message)],
            created=0,
            id="test",
            model=model,
            usage=make_usage(),
        )

    def stream_chat_completion(self, *args, **kwargs):
        raise NotImplementedError

    def supports_streaming(self):
        return False


class RecordingMessageListBuilder:
    """Records calls and returns configurable system message and messages."""

    def __init__(
        self,
        system_message: SystemMessage | None = None,
        messages: list[Message] | None = None,
    ):
        self._system_message = system_message or SystemMessage(
            content=[TextChunk(text="system prompt")]
        )
        self._messages = messages if messages is not None else []
        self.calls: list[dict] = []

    def __call__(
        self,
        conversation: Conversation,
        system_message: str | None,
        turns: int | None = None,
    ) -> tuple[SystemMessage | None, list[Message]]:
        self.calls.append(
            {
                "conversation": conversation,
                "system_message": system_message,
                "turns": turns,
            }
        )
        return self._system_message, list(self._messages)


def make_config(
    model: str = "test-model",
    model_options: dict[str, Any] | None = None,
    system_prompt: str = "You are a helpful assistant.",
    instruction: str = "Do the work",
    iterations: int = 5,
) -> ToolLoopRunnerOptions:
    return ToolLoopRunnerOptions(
        model=model,
        model_options=model_options,
        system_prompt=system_prompt,
        instruction=instruction,
        iterations=iterations,
    )


def make_runner(
    fake: FakeChatCompletions,
    config: ToolLoopRunnerOptions | None = None,
    message_list_builder: RecordingMessageListBuilder | None = None,
) -> ToolLoopRunner:
    return ToolLoopRunner(
        options=config or make_config(),
        chat_completions=fake,
        message_list_builder=message_list_builder or RecordingMessageListBuilder(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestToolLoopRunnerOptions:
    def test_required_fields(self):
        config = ToolLoopRunnerOptions(
            model="my-model",
            system_prompt="system",
            instruction="do it",
            iterations=3,
        )
        assert config.model == "my-model"
        assert config.model_options is None
        assert config.system_prompt == "system"
        assert config.instruction == "do it"
        assert config.iterations == 3

    def test_model_options_defaults_to_none(self):
        config = make_config()
        assert config.model_options is None

    def test_model_options_can_be_set(self):
        config = make_config(model_options={"temperature": 0.7})
        assert config.model_options == {"temperature": 0.7}

    def test_missing_required_field_raises(self):
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ToolLoopRunnerOptions(
                # missing model
                system_prompt="system",
                instruction="do it",
                iterations=3,
            )


class TestToolLoopRunnerInit:
    def test_creates_toolbox_with_task_list_toolset(self):
        fake = FakeChatCompletions([text_response("done")])
        runner = make_runner(fake)
        # The toolbox should contain task list tools
        tool_names = {t.function.name for t in runner._toolbox.tool_descriptions}
        assert tool_names == {
            "add_tasks",
            "complete_tasks",
            "delete_tasks",
            "clear_tasks",
            "clear_completed_tasks",
        }

    def test_stores_options(self):
        fake = FakeChatCompletions([text_response("done")])
        config = make_config(model="my-model", iterations=10)
        runner = make_runner(fake, config=config)
        assert runner._options is config

    def test_stores_chat_completions(self):
        fake = FakeChatCompletions([text_response("done")])
        runner = make_runner(fake)
        assert runner._chat_completions is fake

    def test_stores_message_list_builder(self):
        fake = FakeChatCompletions([text_response("done")])
        builder = RecordingMessageListBuilder()
        runner = make_runner(fake, message_list_builder=builder)
        assert runner._message_list_builder is builder


class TestToolLoopRunnerRun:
    def test_calls_message_list_builder_with_correct_args(self):
        fake = FakeChatCompletions([text_response("done")])
        builder = RecordingMessageListBuilder()
        config = make_config(
            system_prompt="custom system prompt",
        )
        runner = make_runner(fake, config=config, message_list_builder=builder)
        conv = make_conversation()

        runner.run(conv, turns=3)

        assert len(builder.calls) == 1
        call = builder.calls[0]
        assert call["conversation"] is conv
        assert call["system_message"] == "custom system prompt"
        assert call["turns"] == 3

    def test_passes_turns_none_to_message_list_builder(self):
        fake = FakeChatCompletions([text_response("done")])
        builder = RecordingMessageListBuilder()
        runner = make_runner(fake, message_list_builder=builder)
        conv = make_conversation()

        runner.run(conv, turns=None)

        assert builder.calls[0]["turns"] is None

    def test_passes_model_to_chat_completion(self):
        fake = FakeChatCompletions([text_response("done")])
        config = make_config(model="my-custom-model")
        runner = make_runner(fake, config=config)
        conv = make_conversation()

        runner.run(conv, turns=None)

        assert fake.calls[0]["model"] == "my-custom-model"

    def test_passes_model_options_to_chat_completion(self):
        fake = FakeChatCompletions([text_response("done")])
        config = make_config(model_options={"temperature": 0.5})
        runner = make_runner(fake, config=config)
        conv = make_conversation()

        runner.run(conv, turns=None)

        assert fake.calls[0]["options"] == {"temperature": 0.5}

    def test_model_options_none_becomes_empty_dict(self):
        fake = FakeChatCompletions([text_response("done")])
        config = make_config(model_options=None)
        runner = make_runner(fake, config=config)
        conv = make_conversation()

        runner.run(conv, turns=None)

        assert fake.calls[0]["options"] == {}

    def test_passes_system_message_to_chat_completion(self):
        fake = FakeChatCompletions([text_response("done")])
        system_msg = SystemMessage(content=[TextChunk(text="test system")])
        builder = RecordingMessageListBuilder(system_message=system_msg)
        runner = make_runner(fake, message_list_builder=builder)
        conv = make_conversation()

        runner.run(conv, turns=None)

        assert fake.calls[0]["system_message"] is system_msg

    def test_passes_iterations_as_max_iterations(self):
        fake = FakeChatCompletions([text_response("done")])
        config = make_config(iterations=7)
        runner = make_runner(fake, config=config)
        conv = make_conversation()

        runner.run(conv, turns=None)

        # The ToolCallLoop appends "Available Budget: {max_iterations}" to the
        # first user message
        first_user_msg = next(
            m for m in fake.calls[0]["messages"] if isinstance(m, UserMessage)
        )
        assert "Available Budget: 7" in message_text(first_user_msg)

    def test_passes_instruction_to_tool_call_loop(self):
        fake = FakeChatCompletions([text_response("done")])
        config = make_config(instruction="Custom instruction here")
        runner = make_runner(fake, config=config)
        conv = make_conversation()

        runner.run(conv, turns=None)

        first_user_msg = next(
            m for m in fake.calls[0]["messages"] if isinstance(m, UserMessage)
        )
        assert "Custom instruction here" in message_text(first_user_msg)

    def test_offers_task_list_tools(self):
        fake = FakeChatCompletions([text_response("done")])
        runner = make_runner(fake)
        conv = make_conversation()

        runner.run(conv, turns=None)

        offered = {t.function.name for t in fake.calls[0]["tools"]}
        assert offered == {
            "add_tasks",
            "complete_tasks",
            "delete_tasks",
            "clear_tasks",
            "clear_completed_tasks",
        }

    def test_executes_tool_calls_from_task_list(self):
        fake = FakeChatCompletions(
            [
                tool_call_response("add_tasks", {"tasks": ["test task"]}, "call_1"),
                text_response("done"),
            ]
        )
        runner = make_runner(fake)
        conv = make_conversation()

        runner.run(conv, turns=None)

        # Task should have been added to the conversation
        assert conv.task_list is not None
        assert len(conv.task_list) == 1
        assert conv.task_list[0].description == "test task"

    def test_message_list_from_builder_is_used(self):
        fake = FakeChatCompletions([text_response("done")])
        existing_msg = UserMessage(content=[TextChunk(text="existing message")])
        builder = RecordingMessageListBuilder(messages=[existing_msg])
        runner = make_runner(fake, message_list_builder=builder)
        conv = make_conversation()

        runner.run(conv, turns=None)

        # The existing message should be in the message list sent to the model
        messages = fake.calls[0]["messages"]
        assert existing_msg in messages

    def test_message_list_grows_across_iterations(self):
        """The instruction and responses are appended to the shared message list."""
        fake = FakeChatCompletions(
            [
                tool_call_response("add_tasks", {"tasks": ["t1"]}, "call_1"),
                text_response("done"),
            ]
        )
        runner = make_runner(fake)
        conv = make_conversation()

        runner.run(conv, turns=None)

        assert len(fake.calls) == 2
        # Second call's message list should extend the first one
        prev_msgs = fake.calls[0]["messages"]
        curr_msgs = fake.calls[1]["messages"]
        assert curr_msgs[: len(prev_msgs)] == prev_msgs

    def test_tool_context_has_conversation(self):
        """The ToolCallContext passed to tools should have the conversation."""
        fake = FakeChatCompletions(
            [
                tool_call_response("add_tasks", {"tasks": ["ctx test"]}, "call_1"),
                text_response("done"),
            ]
        )
        runner = make_runner(fake)
        conv = make_conversation()

        runner.run(conv, turns=None)

        # If the context didn't have the conversation, add_tasks would fail
        # and the task wouldn't be added
        assert conv.task_list is not None
        assert len(conv.task_list) == 1
        assert conv.task_list[0].description == "ctx test"

    def test_tool_context_is_not_interactive(self):
        """ToolCallContext should have is_interactive=False."""
        fake = FakeChatCompletions(
            [
                tool_call_response("add_tasks", {"tasks": ["t"]}, "call_1"),
                text_response("done"),
            ]
        )
        runner = make_runner(fake)
        conv = make_conversation()

        # This should not raise or hang waiting for input
        runner.run(conv, turns=None)

        assert len(fake.calls) == 2

    def test_iteration_cap_respected(self):
        # Model keeps calling tools forever
        fake = FakeChatCompletions(
            [
                tool_call_response("add_tasks", {"tasks": ["x"]}, f"call_{i}")
                for i in range(20)
            ]
        )
        config = make_config(iterations=3)
        runner = make_runner(fake, config=config)
        conv = make_conversation()

        runner.run(conv, turns=None)

        # Should stop after 3 iterations
        assert len(fake.calls) == 3
        assert conv.task_list is not None
        assert len(conv.task_list) == 3

    def test_uses_default_message_list_builder_compatibility(self):
        """ToolLoopRunner should work with DefaultMessageListBuilder."""
        fake = FakeChatCompletions([text_response("done")])
        config = make_config(system_prompt="You are helpful.")
        runner = ToolLoopRunner(
            options=config,
            chat_completions=fake,
            message_list_builder=DefaultMessageListBuilder(),
        )
        conv = make_conversation()

        runner.run(conv, turns=None)

        assert len(fake.calls) == 1
        # System message should contain the system prompt
        system_text = message_text(fake.calls[0]["system_message"])
        assert "You are helpful." in system_text