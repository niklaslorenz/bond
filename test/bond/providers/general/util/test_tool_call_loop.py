"""Tests for bond.providers.general.util.tool_call_loop module."""

from typing import Any

from returns.result import Failure, Success

from bond.conversation.types import (
    AssistantMessage,
    FunctionCall,
    Message,
    SystemMessage,
    TextChunk,
    ToolCall,
    ToolMessage,
    UsageInfo,
)
from bond.endpoints.chat_completions import (
    CompletionChoice,
    CompletionResponse,
)
from bond.providers.general.util.tool_call_loop import ToolCallLoop
from bond.tools.tool import FunctionParameter, ToolCallContext, tool
from bond.tools.toolbox import PythonToolset, Toolbox

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


def make_tool_call(
    name: str = "test_tool",
    arguments: dict | None = None,
    call_id: str = "call_123",
) -> ToolCall:
    return ToolCall(
        id=call_id,
        function=FunctionCall(name=name, arguments=arguments or {}),
    )


def make_completion_response(
    text: str | None = "Response",
    tool_calls: list[ToolCall] | None = None,
    finish_reason: str = "stop",
) -> CompletionResponse:
    """Create a CompletionResponse for testing."""
    return CompletionResponse(
        choices=[
            CompletionChoice(
                finish_reason=finish_reason,  # type: ignore[arg-type]
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


def make_system_message(text: str = "You are helpful") -> SystemMessage:
    return SystemMessage(content=[TextChunk(text=text)])


def make_tool_context() -> ToolCallContext:
    """Create a minimal ToolCallContext for testing."""
    return ToolCallContext(
        persona=None,
        stdout=None,
        stdin=None,
        is_interactive=False,
        cwd=None,
        logger=None,
        confirmation_prompt=None,
        conversation=None,
    )


def make_test_tool(
    name: str = "test_tool",
    return_value: str | None = "Tool output",
) -> Any:
    """Create a simple test tool using the @tool decorator."""

    @tool(
        name=name,
        description="A test tool",
        parameters={
            "arg1": FunctionParameter(type="string", description="First argument"),
        },
        required=["arg1"],
    )
    def test_tool_fn(context: ToolCallContext, arg1: str) -> str | None:
        return return_value

    return test_tool_fn


def make_failing_tool(name: str = "failing_tool") -> Any:
    """Create a tool that raises an exception."""

    @tool(
        name=name,
        description="A failing test tool",
        parameters={},
    )
    def failing_tool_fn(context: ToolCallContext) -> str:
        raise ValueError("Tool failed!")

    return failing_tool_fn


def make_toolbox_with_tools(tools: list) -> Toolbox:
    """Create a Toolbox with the given tools."""
    toolset = PythonToolset("test-toolset", tools)
    return Toolbox([toolset])


class MockChatCompletionsEndpoint:
    """A mock ChatCompletionsEndpoint for testing."""

    def __init__(self, responses: list[CompletionResponse] | None = None):
        """Initialize with a list of responses to return in sequence."""
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
                "messages": messages,
                "tools": tools,
                "system_message": system_message,
                "options": options,
                "max_retries": max_retries,
            }
        )
        if self._call_count < len(self._responses):
            response = self._responses[self._call_count]
        else:
            # Default: return a response with no tool calls
            response = make_completion_response(text="Done")
        self._call_count += 1
        return response

    def stream_chat_completion(self, *args, **kwargs):
        raise NotImplementedError

    def supports_streaming(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# ToolCallLoop - initialization
# ---------------------------------------------------------------------------


class TestToolCallLoopInit:
    def test_stores_toolbox(self):
        toolbox = make_toolbox_with_tools([])
        endpoint = MockChatCompletionsEndpoint()
        loop = ToolCallLoop(toolbox, endpoint)
        assert loop._toolbox is toolbox

    def test_stores_chat_completions(self):
        toolbox = make_toolbox_with_tools([])
        endpoint = MockChatCompletionsEndpoint()
        loop = ToolCallLoop(toolbox, endpoint)
        assert loop._chat_completions is endpoint


# ---------------------------------------------------------------------------
# ToolCallLoop - run with no tool calls
# ---------------------------------------------------------------------------


class TestToolCallLoopNoToolCalls:
    def test_returns_empty_list_when_no_tool_calls(self):
        toolbox = make_toolbox_with_tools([])
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Hello!", tool_calls=None)]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        result = loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        assert isinstance(result, Success)
        assert result.unwrap() == []

    def test_appends_assistant_message_to_message_list(self):
        toolbox = make_toolbox_with_tools([])
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Hello!")]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        assert len(message_list) == 1
        assert isinstance(message_list[0], AssistantMessage)

    def test_calls_endpoint_with_correct_parameters(self):
        toolbox = make_toolbox_with_tools([])
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Hello!")]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        system_msg = make_system_message("System prompt")
        loop.run(
            model="my-model",
            model_options={"temperature": 0.5},
            message_list=message_list,
            system_msg=system_msg,
            tool_context=make_tool_context(),
            max_iterations=5,
            max_retries=5,
        )

        assert len(endpoint.calls) == 1
        call = endpoint.calls[0]
        assert call["model"] == "my-model"
        assert call["options"] == {"temperature": 0.5}
        assert call["system_message"] is system_msg
        assert call["max_retries"] == 5


# ---------------------------------------------------------------------------
# ToolCallLoop - run with tool calls
# ---------------------------------------------------------------------------


class TestToolCallLoopWithToolCalls:
    def test_executes_single_tool_call(self):
        test_tool = make_test_tool("my_tool", return_value="Tool result")
        toolbox = make_toolbox_with_tools([test_tool])
        tool_call = make_tool_call("my_tool", {"arg1": "value1"}, call_id="call_1")
        endpoint = MockChatCompletionsEndpoint(
            responses=[
                make_completion_response(
                    text="Calling tool...", tool_calls=[tool_call], finish_reason="tool_calls"
                ),
                make_completion_response(text="Done after tool"),
            ]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        result = loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        assert isinstance(result, Success)
        tool_calls_result = result.unwrap()
        assert len(tool_calls_result) == 1
        assert tool_calls_result[0][0] is tool_call
        assert isinstance(tool_calls_result[0][1], ToolMessage)
        assert tool_calls_result[0][1].content[0].text == "Tool result"

    def test_appends_tool_message_to_message_list(self):
        test_tool = make_test_tool("my_tool", return_value="Result")
        toolbox = make_toolbox_with_tools([test_tool])
        tool_call = make_tool_call("my_tool", {"arg1": "val"}, call_id="call_1")
        endpoint = MockChatCompletionsEndpoint(
            responses=[
                make_completion_response(
                    text=None, tool_calls=[tool_call], finish_reason="tool_calls"
                ),
                make_completion_response(text="Done"),
            ]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        # Should have: assistant message with tool call, tool message, final assistant message
        assert len(message_list) == 3
        assert isinstance(message_list[0], AssistantMessage)
        assert isinstance(message_list[1], ToolMessage)
        assert isinstance(message_list[2], AssistantMessage)

    def test_executes_multiple_tool_calls_in_one_response(self):
        test_tool = make_test_tool("my_tool", return_value="Result")
        toolbox = make_toolbox_with_tools([test_tool])
        tool_call_1 = make_tool_call("my_tool", {"arg1": "1"}, call_id="call_1")
        tool_call_2 = make_tool_call("my_tool", {"arg1": "2"}, call_id="call_2")
        endpoint = MockChatCompletionsEndpoint(
            responses=[
                make_completion_response(
                    text=None,
                    tool_calls=[tool_call_1, tool_call_2],
                    finish_reason="tool_calls",
                ),
                make_completion_response(text="Done"),
            ]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        result = loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        assert isinstance(result, Success)
        tool_calls_result = result.unwrap()
        assert len(tool_calls_result) == 2

    def test_multiple_iterations_with_tool_calls(self):
        """Test that the loop continues until no more tool calls or max_iterations."""
        test_tool = make_test_tool("my_tool", return_value="Result")
        toolbox = make_toolbox_with_tools([test_tool])
        tool_call_1 = make_tool_call("my_tool", {"arg1": "1"}, call_id="call_1")
        tool_call_2 = make_tool_call("my_tool", {"arg1": "2"}, call_id="call_2")
        endpoint = MockChatCompletionsEndpoint(
            responses=[
                make_completion_response(
                    text=None, tool_calls=[tool_call_1], finish_reason="tool_calls"
                ),
                make_completion_response(
                    text=None, tool_calls=[tool_call_2], finish_reason="tool_calls"
                ),
                make_completion_response(text="All done"),
            ]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        result = loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        assert isinstance(result, Success)
        tool_calls_result = result.unwrap()
        assert len(tool_calls_result) == 2
        assert endpoint._call_count == 3  # 2 tool calls + 1 final response

    def test_tool_message_preserves_tool_call_metadata(self):
        test_tool = make_test_tool("my_tool", return_value="Result")
        toolbox = make_toolbox_with_tools([test_tool])
        tool_call = make_tool_call("my_tool", {"arg1": "val"}, call_id="call_xyz")
        endpoint = MockChatCompletionsEndpoint(
            responses=[
                make_completion_response(
                    text=None, tool_calls=[tool_call], finish_reason="tool_calls"
                ),
                make_completion_response(text="Done"),
            ]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        result = loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        tool_message = result.unwrap()[0][1]
        assert tool_message.name == "my_tool"
        assert tool_message.tool_call_id == "call_xyz"


# ---------------------------------------------------------------------------
# ToolCallLoop - max_iterations
# ---------------------------------------------------------------------------


class TestToolCallLoopMaxIterations:
    def test_stops_at_max_iterations(self):
        """Even if the model keeps requesting tool calls, stop at max_iterations."""
        test_tool = make_test_tool("my_tool", return_value="Result")
        toolbox = make_toolbox_with_tools([test_tool])
        tool_call = make_tool_call("my_tool", {"arg1": "val"}, call_id="call_1")
        # All responses have tool calls
        endpoint = MockChatCompletionsEndpoint(
            responses=[
                make_completion_response(
                    text=None, tool_calls=[tool_call], finish_reason="tool_calls"
                )
                for _ in range(10)
            ]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        result = loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=3,
        )

        assert isinstance(result, Success)
        tool_calls_result = result.unwrap()
        assert len(tool_calls_result) == 3
        assert endpoint._call_count == 3  # Stopped at max_iterations

    def test_max_iterations_one(self):
        """With max_iterations=1, only one call is made."""
        test_tool = make_test_tool("my_tool", return_value="Result")
        toolbox = make_toolbox_with_tools([test_tool])
        tool_call = make_tool_call("my_tool", {"arg1": "val"}, call_id="call_1")
        endpoint = MockChatCompletionsEndpoint(
            responses=[
                make_completion_response(
                    text=None, tool_calls=[tool_call], finish_reason="tool_calls"
                ),
                make_completion_response(text="Done"),
            ]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        result = loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=1,
        )

        assert isinstance(result, Success)
        assert len(result.unwrap()) == 1
        assert endpoint._call_count == 1


# ---------------------------------------------------------------------------
# ToolCallLoop - error handling
# ---------------------------------------------------------------------------


class TestToolCallLoopErrorHandling:
    def test_returns_failure_when_endpoint_raises(self):
        toolbox = make_toolbox_with_tools([])

        class FailingEndpoint:
            def chat_completion(self, *args, **kwargs):
                raise RuntimeError("API is down")

            def stream_chat_completion(self, *args, **kwargs):
                raise NotImplementedError

            def supports_streaming(self) -> bool:
                return False

        endpoint = FailingEndpoint()
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        result = loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        assert isinstance(result, Failure)
        assert "Endpoint error during tool call loop" in result.failure()
        assert "API is down" in result.failure()

    def test_continues_when_tool_fails(self):
        """If a tool raises an exception, the loop should continue with the error as output."""
        failing_tool = make_failing_tool("failing_tool")
        toolbox = make_toolbox_with_tools([failing_tool])
        tool_call = make_tool_call("failing_tool", {}, call_id="call_1")
        endpoint = MockChatCompletionsEndpoint(
            responses=[
                make_completion_response(
                    text=None, tool_calls=[tool_call], finish_reason="tool_calls"
                ),
                make_completion_response(text="Done"),
            ]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        result = loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        assert isinstance(result, Success)
        tool_calls_result = result.unwrap()
        assert len(tool_calls_result) == 1
        # The tool message should contain the error
        tool_message = tool_calls_result[0][1]
        assert "Failure" in tool_message.content[0].text
        assert "Tool failed!" in tool_message.content[0].text

    def test_unknown_tool_returns_failure_message(self):
        """If the model calls an unknown tool, the error should be in the tool message."""
        toolbox = make_toolbox_with_tools([])  # No tools
        tool_call = make_tool_call("unknown_tool", {}, call_id="call_1")
        endpoint = MockChatCompletionsEndpoint(
            responses=[
                make_completion_response(
                    text=None, tool_calls=[tool_call], finish_reason="tool_calls"
                ),
                make_completion_response(text="Done"),
            ]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        result = loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        assert isinstance(result, Success)
        tool_message = result.unwrap()[0][1]
        assert "Failure" in tool_message.content[0].text
        assert "Invalid tool name" in tool_message.content[0].text


# ---------------------------------------------------------------------------
# ToolCallLoop - max_retries parameter
# ---------------------------------------------------------------------------


class TestToolCallLoopMaxRetries:
    def test_passes_max_retries_to_endpoint(self):
        toolbox = make_toolbox_with_tools([])
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
            max_retries=7,
        )

        assert endpoint.calls[0]["max_retries"] == 7

    def test_default_max_retries_is_3(self):
        toolbox = make_toolbox_with_tools([])
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        assert endpoint.calls[0]["max_retries"] == 3


# ---------------------------------------------------------------------------
# ToolCallLoop - tool_descriptions passed to endpoint
# ---------------------------------------------------------------------------


class TestToolCallLoopToolDescriptions:
    def test_passes_tool_descriptions_to_endpoint(self):
        test_tool = make_test_tool("my_tool")
        toolbox = make_toolbox_with_tools([test_tool])
        endpoint = MockChatCompletionsEndpoint(
            responses=[make_completion_response(text="Done")]
        )
        loop = ToolCallLoop(toolbox, endpoint)

        message_list: list[Message] = []
        loop.run(
            model="test-model",
            model_options={},
            message_list=message_list,
            system_msg=make_system_message(),
            tool_context=make_tool_context(),
            max_iterations=5,
        )

        tools = endpoint.calls[0]["tools"]
        assert len(tools) == 1
        assert tools[0].function.name == "my_tool"
