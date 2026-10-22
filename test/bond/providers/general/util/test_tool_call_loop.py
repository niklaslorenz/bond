"""Tests for bond.providers.general.util.tool_call_loop module."""

from returns.result import Failure, Success

from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantMessage,
    FunctionCall,
    SystemMessage,
    TextChunk,
    ToolCall,
    ToolMessage,
    UsageInfo,
    UserMessage,
)
from bond.endpoints.chat_completions import CompletionChoice, CompletionResponse
from bond.providers.general.util.tool_call_loop import ToolCallLoop
from bond.tools import tool
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import PythonToolset, Toolbox

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_usage(total_tokens: int = 30) -> UsageInfo:
    return UsageInfo(completion_tokens=10, prompt_tokens=20, total_tokens=total_tokens)


def make_conversation() -> Conversation:
    return Conversation()


@tool.tool(
    name="record_note",
    description="Record a note for testing.",
    parameters={
        "note": tool.FunctionParameter(
            type="string",
            description="The note to record",
        ),
    },
    required=["note"],
)
def record_note(context: ToolCallContext, note: str) -> str:
    """Record a note."""
    return f"recorded: {note}"


@tool.tool(
    name="failing_tool",
    description="Always fails.",
    parameters={},
)
def failing_tool(context: ToolCallContext) -> str:
    """Always fails."""
    raise RuntimeError("boom")


def make_toolbox() -> Toolbox:
    return Toolbox(
        [
            PythonToolset(
                "test_tools",
                [record_note, failing_tool],
            )
        ]
    )


def text_response(text: str) -> AssistantMessage:
    return AssistantMessage(content=[TextChunk(text=text)])


def tool_call_response(name: str, arguments: dict, call_id: str) -> AssistantMessage:
    return AssistantMessage(
        tool_calls=[
            ToolCall(id=call_id, function=FunctionCall(name=name, arguments=arguments))
        ]
    )


class FakeChatCompletions:
    """Returns scripted responses in order and records every call.

    Each call captures a *snapshot* of the message list (the loop mutates
    the same list across iterations, so we must copy at call time).
    """

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


class RaisingChatCompletions:
    """Always raises on chat_completion, simulating an endpoint failure."""

    def __init__(self, exception: Exception | None = None):
        self.exception = exception or RuntimeError("endpoint exploded")
        self.calls = 0

    def chat_completion(self, *args, **kwargs):
        self.calls += 1
        raise self.exception

    def stream_chat_completion(self, *args, **kwargs):
        raise NotImplementedError

    def supports_streaming(self):
        return False


def make_loop(fake: FakeChatCompletions) -> ToolCallLoop:
    return ToolCallLoop(make_toolbox(), fake)


def make_system_msg() -> SystemMessage:
    return SystemMessage(content=[TextChunk(text="system prompt")])


def make_tool_context(conv: Conversation) -> ToolCallContext:
    return ToolCallContext.default(None, False, conv)


def message_text(msg) -> str:
    return "".join(
        chunk.text for chunk in (msg.content or []) if isinstance(chunk, TextChunk)
    )


def assert_tool_calls_balanced(messages):
    """Every assistant tool_call must be followed by a matching tool message."""
    pending: list[str | None] = []
    for msg in messages:
        if isinstance(msg, AssistantMessage) and msg.tool_calls:
            pending.extend(call.id for call in msg.tool_calls)
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


class TestToolCallLoop:
    def test_appends_instruction_with_budget_and_returns_empty_on_text(self):
        fake = FakeChatCompletions([text_response("done")])
        loop = make_loop(fake)
        messages: list = []

        result = loop.run(
            model="test-model",
            model_options={},
            message_list=messages,
            system_msg=make_system_msg(),
            instruction="Do the thing",
            tool_context=make_tool_context(Conversation()),
            max_iterations=5,
        )

        assert isinstance(result, Success)
        assert result.unwrap() == []
        # Instruction with budget was appended, then the assistant message
        assert len(messages) == 2
        assert isinstance(messages[0], UserMessage)
        assert message_text(messages[0]) == "Do the thing\nAvailable Budget: 5"
        assert isinstance(messages[1], AssistantMessage)
        assert message_text(messages[1]) == "done"

    def test_executes_tool_calls_and_returns_pairs(self):
        fake = FakeChatCompletions(
            [
                tool_call_response("record_note", {"note": "hello"}, "call_1"),
                text_response("done"),
            ]
        )
        loop = make_loop(fake)
        messages: list = []

        result = loop.run(
            model="test-model",
            model_options={},
            message_list=messages,
            system_msg=make_system_msg(),
            instruction="Record a note",
            tool_context=make_tool_context(Conversation()),
            max_iterations=5,
        )

        pairs = result.unwrap()
        assert len(pairs) == 1
        tool_call, tool_message = pairs[0]
        assert tool_call.id == "call_1"
        assert tool_call.function.name == "record_note"
        assert isinstance(tool_message, ToolMessage)
        assert tool_message.tool_call_id == "call_1"
        assert tool_message.name == "record_note"
        assert message_text(tool_message) == "recorded: hello"

        # Message list: user instruction, assistant(tool call), tool response,
        # user budget notification, assistant(text)
        assert len(messages) == 5
        assert_tool_calls_balanced(messages)

    def test_offers_all_tools_from_toolbox(self):
        fake = FakeChatCompletions([text_response("done")])
        loop = make_loop(fake)

        loop.run(
            model="test-model",
            model_options={},
            message_list=[],
            system_msg=make_system_msg(),
            instruction="instr",
            tool_context=make_tool_context(Conversation()),
            max_iterations=5,
        )

        offered = {t.function.name for t in fake.calls[0]["tools"]}
        assert offered == {"record_note", "failing_tool"}

    def test_passes_parameters_through_to_endpoint(self):
        fake = FakeChatCompletions([text_response("done")])
        loop = make_loop(fake)
        system_msg = make_system_msg()
        options = {"temperature": 0.5}

        loop.run(
            model="my-model",
            model_options=options,
            message_list=[],
            system_msg=system_msg,
            instruction="instr",
            tool_context=make_tool_context(Conversation()),
            max_iterations=3,
            max_retries=7,
        )

        call = fake.calls[0]
        assert call["model"] == "my-model"
        assert call["options"] == {"temperature": 0.5}
        assert call["system_message"] is system_msg
        assert call["max_retries"] == 7

    def test_prefix_extends_across_iterations(self):
        """Each iteration's message list must extend the previous one,
        which is what makes the provider's prefix KV cache effective."""
        fake = FakeChatCompletions(
            [
                tool_call_response("record_note", {"note": "a"}, "call_1"),
                tool_call_response("record_note", {"note": "b"}, "call_2"),
                text_response("done"),
            ]
        )
        loop = make_loop(fake)
        messages: list = []

        loop.run(
            model="test-model",
            model_options={},
            message_list=messages,
            system_msg=make_system_msg(),
            instruction="Record notes",
            tool_context=make_tool_context(Conversation()),
            max_iterations=5,
        )

        assert len(fake.calls) == 3
        for prev, curr in zip(fake.calls, fake.calls[1:]):
            prev_msgs = prev["messages"]
            curr_msgs = curr["messages"]
            assert curr_msgs[: len(prev_msgs)] == prev_msgs

    def test_message_list_stays_balanced_across_iterations(self):
        fake = FakeChatCompletions(
            [
                tool_call_response("record_note", {"note": "a"}, "call_1"),
                tool_call_response("record_note", {"note": "b"}, "call_2"),
                text_response("done"),
            ]
        )
        loop = make_loop(fake)
        messages: list = []

        loop.run(
            model="test-model",
            model_options={},
            message_list=messages,
            system_msg=make_system_msg(),
            instruction="Record notes",
            tool_context=make_tool_context(Conversation()),
            max_iterations=5,
        )

        assert_tool_calls_balanced(messages)

    def test_iteration_cap_stops_loop_and_keeps_list_balanced(self):
        # Model keeps calling tools forever; the loop must stop at the cap
        fake = FakeChatCompletions(
            [
                tool_call_response("record_note", {"note": "x"}, f"call_{i}")
                for i in range(10)
            ]
        )
        loop = make_loop(fake)
        messages: list = []

        result = loop.run(
            model="test-model",
            model_options={},
            message_list=messages,
            system_msg=make_system_msg(),
            instruction="Record notes",
            tool_context=make_tool_context(Conversation()),
            max_iterations=3,
        )

        # Loop stopped after 3 iterations despite pending tool calls
        assert len(fake.calls) == 3
        assert len(result.unwrap()) == 3
        # Every executed tool call still got its response appended
        assert_tool_calls_balanced(messages)

    def test_tool_failure_becomes_failure_text_in_tool_message(self):
        fake = FakeChatCompletions(
            [
                tool_call_response("failing_tool", {}, "call_1"),
                text_response("done"),
            ]
        )
        loop = make_loop(fake)
        messages: list = []

        result = loop.run(
            model="test-model",
            model_options={},
            message_list=messages,
            system_msg=make_system_msg(),
            instruction="instr",
            tool_context=make_tool_context(Conversation()),
            max_iterations=5,
        )

        pairs = result.unwrap()
        assert len(pairs) == 1
        _, tool_message = pairs[0]
        assert message_text(tool_message).startswith("Failure:")
        assert "boom" in message_text(tool_message)
        assert_tool_calls_balanced(messages)

    def test_unknown_tool_becomes_failure_text(self):
        fake = FakeChatCompletions(
            [
                tool_call_response("nonexistent_tool", {}, "call_1"),
                text_response("done"),
            ]
        )
        loop = make_loop(fake)
        messages: list = []

        result = loop.run(
            model="test-model",
            model_options={},
            message_list=messages,
            system_msg=make_system_msg(),
            instruction="instr",
            tool_context=make_tool_context(Conversation()),
            max_iterations=5,
        )

        pairs = result.unwrap()
        assert len(pairs) == 1
        _, tool_message = pairs[0]
        assert message_text(tool_message).startswith("Failure:")
        assert_tool_calls_balanced(messages)

    def test_budget_countdown_messages_between_iterations(self):
        fake = FakeChatCompletions(
            [
                tool_call_response("record_note", {"note": "a"}, "call_1"),
                tool_call_response("record_note", {"note": "b"}, "call_2"),
                text_response("done"),
            ]
        )
        loop = make_loop(fake)
        messages: list = []

        loop.run(
            model="test-model",
            model_options={},
            message_list=messages,
            system_msg=make_system_msg(),
            instruction="instr",
            tool_context=make_tool_context(Conversation()),
            max_iterations=5,
        )

        user_messages = [m for m in messages if isinstance(m, UserMessage)]
        texts = [message_text(m) for m in user_messages]
        assert texts[0] == "instr\nAvailable Budget: 5"
        # Countdown messages appear before iterations 2 and 3
        assert "Available Budget: 4" in texts
        assert "Available Budget: 3" in texts

    def test_multiple_tool_calls_in_one_message_all_executed(self):
        response = AssistantMessage(
            tool_calls=[
                ToolCall(
                    id="call_a",
                    function=FunctionCall(name="record_note", arguments={"note": "a"}),
                ),
                ToolCall(
                    id="call_b",
                    function=FunctionCall(name="record_note", arguments={"note": "b"}),
                ),
            ]
        )
        fake = FakeChatCompletions([response, text_response("done")])
        loop = make_loop(fake)
        messages: list = []

        result = loop.run(
            model="test-model",
            model_options={},
            message_list=messages,
            system_msg=make_system_msg(),
            instruction="instr",
            tool_context=make_tool_context(Conversation()),
            max_iterations=5,
        )

        pairs = result.unwrap()
        assert len(pairs) == 2
        outputs = [message_text(tm) for _, tm in pairs]
        assert "recorded: a" in outputs[0]
        assert "recorded: b" in outputs[1]
        assert_tool_calls_balanced(messages)

    def test_tool_arguments_passed_through(self):
        fake = FakeChatCompletions(
            [
                tool_call_response(
                    "record_note", {"note": "specific note text"}, "call_1"
                ),
                text_response("done"),
            ]
        )
        loop = make_loop(fake)

        result = loop.run(
            model="test-model",
            model_options={},
            message_list=[],
            system_msg=make_system_msg(),
            instruction="instr",
            tool_context=make_tool_context(Conversation()),
            max_iterations=5,
        )

        _, tool_message = result.unwrap()[0]
        assert message_text(tool_message) == "recorded: specific note text"
