"""Tests for bond.providers.general.summarization module."""

from typing import Any

from returns.result import Failure, Success

from bond.conversation.conversation import Conversation
from bond.conversation.task_list import TaskList
from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    FunctionCall,
    Message,
    SystemMessage,
    TextChunk,
    ThinkChunk,
    ToolCall,
    Turn,
    UsageInfo,
    UserConversationMessage,
    UserMessage,
)
from bond.conversation.working_set import WorkingSet
from bond.endpoints.chat_completions import CompletionChoice, CompletionResponse
from bond.providers.general.summarization import (
    DefaultSummarizationCapability,
    DefaultSummarizationOptions,
    EpisodeSummarizationOptions,
    SummaryHandlerOptions,
    ThoughtCondensationOptions,
)
from bond.providers.general.util.default_message_list_builder import (
    DefaultMessageListBuilder,
)
from bond.providers.general.util.tool_loop_runner import ToolLoopRunnerOptions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_usage(
    total_tokens: int = 30, completion_tokens: int = 10, prompt_tokens: int = 20
) -> UsageInfo:
    return UsageInfo(
        completion_tokens=completion_tokens,
        prompt_tokens=prompt_tokens,
        total_tokens=total_tokens,
    )


def make_turn(
    user_text: str = "hello",
    assistant_text: str = "hi",
    usage: UsageInfo | None = None,
) -> Turn:
    return Turn(
        user_message=UserConversationMessage(
            message=UserMessage.create(user_text),
            name="user",
        ),
        assistant_response=AssistantConversationMessage(
            message=AssistantMessage(content=[TextChunk(text=assistant_text)]),
            name="assistant",
            usage=usage or make_usage(),
        ),
    )


def make_conversation(n_turns: int = 3, usage: UsageInfo | None = None) -> Conversation:
    conv = Conversation()
    for i in range(n_turns):
        conv.add_turn(make_turn(f"message {i}", f"reply {i}", usage))
    return conv


def make_thought_turn(
    thoughts: str = "Let me think about this...",
    response: str = "Here's my answer",
    usage: UsageInfo | None = None,
) -> Turn:
    return Turn(
        user_message=UserConversationMessage(
            message=UserMessage.create("question"),
            name="user",
        ),
        assistant_response=AssistantConversationMessage(
            message=AssistantMessage(
                content=[
                    ThinkChunk(thinking=[TextChunk(text=thoughts)]),
                    TextChunk(text=response),
                ]
            ),
            name="assistant",
            usage=usage or make_usage(),
        ),
    )


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


def make_summary_handler(
    model: str = "summary-model",
    prompt: str = "Summarize the conversation.",
    instruction: str = "Summarize the conversation above.",
    model_options: dict[str, Any] | None = None,
) -> SummaryHandlerOptions:
    return SummaryHandlerOptions(
        model=model,
        model_options=model_options,
        prompt=prompt,
        instruction=instruction,
    )


def make_task_list_handler(
    model: str = "task-model",
    iterations: int = 5,
) -> ToolLoopRunnerOptions:
    return ToolLoopRunnerOptions(
        model=model,
        system_prompt="Update the task list.",
        instruction="Review and update the task list.",
        iterations=iterations,
    )


def make_working_set_handler(
    model: str = "ws-model",
    iterations: int = 5,
) -> ToolLoopRunnerOptions:
    return ToolLoopRunnerOptions(
        model=model,
        system_prompt="Update the working set.",
        instruction="Review and update the working set.",
        iterations=iterations,
    )


def make_episode_summarization_options(
    token_threshold: int = 100,
    keep_turns: int = 1,
    min_summarized_turns: int = 1,
    task_list_handler: ToolLoopRunnerOptions | None = None,
    working_set_handler: ToolLoopRunnerOptions | None = None,
    summary_handler: SummaryHandlerOptions | None = None,
) -> EpisodeSummarizationOptions:
    return EpisodeSummarizationOptions(
        token_threshold=token_threshold,
        keep_turns=keep_turns,
        min_summarized_turns=min_summarized_turns,
        task_list_handler=task_list_handler,
        working_set_handler=working_set_handler,
        summary_handler=summary_handler or make_summary_handler(),
    )


def make_config(
    thought_condensation: ThoughtCondensationOptions | None = None,
    episode_summarization: EpisodeSummarizationOptions | None = None,
) -> DefaultSummarizationOptions:
    return DefaultSummarizationOptions(
        thought_condensation=thought_condensation,
        episode_summarization=episode_summarization,
    )


def make_capability(
    fake: FakeChatCompletions,
    config: DefaultSummarizationOptions | None = None,
    message_list_builder: RecordingMessageListBuilder | None = None,
) -> DefaultSummarizationCapability:
    return DefaultSummarizationCapability(
        config=config or make_config(episode_summarization=make_episode_summarization_options()),
        chat_completions=fake,
        message_list_builder=message_list_builder or RecordingMessageListBuilder(),
    )


# ---------------------------------------------------------------------------
# Tests: Options classes
# ---------------------------------------------------------------------------


class TestThoughtCondensationOptions:
    def test_required_fields(self):
        opts = ThoughtCondensationOptions(
            model="model",
            prompt="prompt",
            token_threshold=100,
        )
        assert opts.model == "model"
        assert opts.model_options is None
        assert opts.prompt == "prompt"
        assert opts.token_threshold == 100

    def test_model_options_can_be_set(self):
        opts = ThoughtCondensationOptions(
            model="model",
            prompt="prompt",
            token_threshold=100,
            model_options={"temperature": 0.5},
        )
        assert opts.model_options == {"temperature": 0.5}


class TestSummaryHandlerOptions:
    def test_required_fields(self):
        opts = SummaryHandlerOptions(
            model="model",
            prompt="prompt",
            instruction="instruction",
        )
        assert opts.model == "model"
        assert opts.model_options is None
        assert opts.prompt == "prompt"
        assert opts.instruction == "instruction"


class TestEpisodeSummarizationOptions:
    def test_required_fields(self):
        opts = make_episode_summarization_options(
            token_threshold=200,
            keep_turns=2,
            min_summarized_turns=3,
        )
        assert opts.token_threshold == 200
        assert opts.keep_turns == 2
        assert opts.min_summarized_turns == 3
        assert opts.task_list_handler is None
        assert opts.working_set_handler is None
        assert opts.summary_handler is not None

    def test_handlers_can_be_set(self):
        tl_handler = make_task_list_handler()
        ws_handler = make_working_set_handler()
        opts = make_episode_summarization_options(
            task_list_handler=tl_handler,
            working_set_handler=ws_handler,
        )
        assert opts.task_list_handler is tl_handler
        assert opts.working_set_handler is ws_handler


class TestDefaultSummarizationOptions:
    def test_both_none_by_default(self):
        opts = DefaultSummarizationOptions()
        assert opts.thought_condensation is None
        assert opts.episode_summarization is None

    def test_can_set_both(self):
        tc = ThoughtCondensationOptions(
            model="model", prompt="prompt", token_threshold=100
        )
        es = make_episode_summarization_options()
        opts = DefaultSummarizationOptions(
            thought_condensation=tc,
            episode_summarization=es,
        )
        assert opts.thought_condensation is tc
        assert opts.episode_summarization is es


# ---------------------------------------------------------------------------
# Tests: DefaultSummarizationCapability initialization
# ---------------------------------------------------------------------------


class TestCapabilityInit:
    def test_no_handlers_when_no_episode_summarization(self):
        fake = FakeChatCompletions([text_response("done")])
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=None),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        assert cap._task_list_handler is None
        assert cap._working_set_handler is None

    def test_no_handlers_when_handlers_not_configured(self):
        fake = FakeChatCompletions([text_response("done")])
        cap = make_capability(fake)
        assert cap._task_list_handler is None
        assert cap._working_set_handler is None

    def test_task_list_handler_created_when_configured(self):
        fake = FakeChatCompletions([text_response("done")])
        es_opts = make_episode_summarization_options(
            task_list_handler=make_task_list_handler(),
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        assert cap._task_list_handler is not None
        assert cap._working_set_handler is None

    def test_working_set_handler_created_when_configured(self):
        fake = FakeChatCompletions([text_response("done")])
        es_opts = make_episode_summarization_options(
            working_set_handler=make_working_set_handler(),
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        assert cap._task_list_handler is None
        assert cap._working_set_handler is not None

    def test_both_handlers_created_when_configured(self):
        fake = FakeChatCompletions([text_response("done")])
        es_opts = make_episode_summarization_options(
            task_list_handler=make_task_list_handler(),
            working_set_handler=make_working_set_handler(),
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        assert cap._task_list_handler is not None
        assert cap._working_set_handler is not None


# ---------------------------------------------------------------------------
# Tests: summarize_episode
# ---------------------------------------------------------------------------


class TestSummarizeEpisode:
    def test_returns_none_without_episode_summarization_config(self):
        fake = FakeChatCompletions([text_response("done")])
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=None),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation()
        result = cap.summarize_episode(conv, force=True)
        assert result is None

    def test_returns_zero_when_no_last_turn(self):
        fake = FakeChatCompletions([text_response("summary")])
        cap = make_capability(fake)
        conv = Conversation()  # empty conversation, no turns
        result = cap.summarize_episode(conv, force=True)
        assert isinstance(result, Success)
        assert result.unwrap() == 0

    def test_returns_zero_when_below_threshold_not_forced(self):
        fake = FakeChatCompletions([text_response("summary")])
        # High threshold, low usage
        es_opts = make_episode_summarization_options(token_threshold=10000)
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3, usage=make_usage(total_tokens=50))
        result = cap.summarize_episode(conv, force=False)
        assert isinstance(result, Success)
        assert result.unwrap() == 0
        assert len(fake.calls) == 0  # no model call made

    def test_runs_when_forced_even_below_threshold(self):
        fake = FakeChatCompletions([text_response("A summary.")])
        es_opts = make_episode_summarization_options(
            token_threshold=10000,  # very high threshold
            keep_turns=1,
            min_summarized_turns=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3, usage=make_usage(total_tokens=50))
        result = cap.summarize_episode(conv, force=True)
        assert isinstance(result, Success)
        assert result.unwrap() == 2  # 3 turns - 1 keep_turn = 2 summarized

    def test_returns_zero_when_not_enough_turns(self):
        fake = FakeChatCompletions([text_response("summary")])
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            keep_turns=1,
            min_summarized_turns=5,  # need at least 5 turns to summarize
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        result = cap.summarize_episode(conv, force=True)
        assert isinstance(result, Success)
        assert result.unwrap() == 0

    def test_returns_failure_when_summarization_fails(self):
        fake = FakeChatCompletions([AssistantMessage(content=None)])
        es_opts = make_episode_summarization_options(token_threshold=1)
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        result = cap.summarize_episode(conv, force=True)
        assert isinstance(result, Failure)

    def test_archives_turns_on_success(self):
        fake = FakeChatCompletions([text_response("A summary.")])
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            keep_turns=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        result = cap.summarize_episode(conv, force=True)
        assert isinstance(result, Success)
        assert result.unwrap() == 2
        # Should have 2 episodes now: finished one with 2 turns, new one with 1 turn
        assert len(conv.episodes) == 2
        finished = conv.episodes[0]
        current = conv.episodes[1]
        assert finished.is_finished
        assert len(finished.turns) == 2
        assert len(current.turns) == 1
        assert current.prefix_summary == "A summary."

    def test_clears_task_list_when_no_handler(self):
        fake = FakeChatCompletions([text_response("A summary.")])
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            keep_turns=1,
            task_list_handler=None,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        conv.task_list = TaskList()
        conv.task_list.add_item("existing task")
        cap.summarize_episode(conv, force=True)
        assert conv.task_list is None

    def test_clears_working_set_when_no_handler(self):
        fake = FakeChatCompletions([text_response("A summary.")])
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            keep_turns=1,
            working_set_handler=None,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        conv.working_set = WorkingSet()
        cap.summarize_episode(conv, force=True)
        assert conv.working_set is None

    def test_runs_task_list_handler_when_configured(self):
        # Summary runs FIRST, then task list handler
        fake = FakeChatCompletions(
            [
                # Summary handler runs first
                text_response("A summary."),
                # Task list handler: add a task, then done
                tool_call_response("add_tasks", {"tasks": ["new task"]}, "call_1"),
                text_response("Task list updated."),
            ]
        )
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            keep_turns=1,
            task_list_handler=make_task_list_handler(iterations=3),
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=DefaultMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        result = cap.summarize_episode(conv, force=True)
        assert isinstance(result, Success)
        assert conv.task_list is not None
        assert len(conv.task_list) == 1
        assert conv.task_list[0].description == "new task"

    def test_updates_task_list_display(self):
        fake = FakeChatCompletions(
            [
                # Summary runs first
                text_response("A summary."),
                # Task list handler
                tool_call_response("add_tasks", {"tasks": ["task 1"]}, "call_1"),
                text_response("done"),
            ]
        )
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            keep_turns=1,
            task_list_handler=make_task_list_handler(iterations=3),
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=DefaultMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        cap.summarize_episode(conv, force=True)
        assert conv.task_list is not None
        assert conv.task_list.displayed is not None
        assert "task 1" in conv.task_list.displayed

    def test_uses_correct_model_for_each_step(self):
        # Summary runs FIRST (summary-model), then task list handler (task-model)
        fake = FakeChatCompletions(
            [
                # Summary handler uses summary-model (runs first)
                text_response("A summary."),
                # Task list handler uses task-model (runs second)
                text_response("no changes"),
            ]
        )
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            keep_turns=1,
            task_list_handler=make_task_list_handler(model="task-model"),
            summary_handler=make_summary_handler(model="summary-model"),
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=DefaultMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        cap.summarize_episode(conv, force=True)
        assert len(fake.calls) == 2
        assert fake.calls[0]["model"] == "summary-model"
        assert fake.calls[1]["model"] == "task-model"

    def test_passes_turns_to_message_list_builder(self):
        fake = FakeChatCompletions([text_response("A summary.")])
        builder = RecordingMessageListBuilder()
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            keep_turns=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=builder,
        )
        conv = make_conversation(n_turns=5)
        cap.summarize_episode(conv, force=True)
        # n_summarized_turns = 5 - 1 = 4
        assert builder.calls[0]["turns"] == 4

    def test_summary_call_has_no_tools(self):
        fake = FakeChatCompletions([text_response("A summary.")])
        es_opts = make_episode_summarization_options(token_threshold=1)
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        cap.summarize_episode(conv, force=True)
        # Summary call should have no tools
        assert fake.calls[0]["tools"] == []

    def test_summary_instruction_appended_as_user_message(self):
        fake = FakeChatCompletions([text_response("A summary.")])
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            summary_handler=make_summary_handler(instruction="CUSTOM INSTRUCTION"),
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        cap.summarize_episode(conv, force=True)
        last_msg = fake.calls[0]["messages"][-1]
        assert isinstance(last_msg, UserMessage)
        assert message_text(last_msg) == "CUSTOM INSTRUCTION"

    def test_summary_prompt_used_as_system_message(self):
        fake = FakeChatCompletions([text_response("A summary.")])
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            summary_handler=make_summary_handler(prompt="CUSTOM PROMPT"),
        )
        builder = RecordingMessageListBuilder()
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=builder,
        )
        conv = make_conversation(n_turns=3)
        cap.summarize_episode(conv, force=True)
        # The builder receives the prompt as system_message string
        assert builder.calls[0]["system_message"] == "CUSTOM PROMPT"

    def test_returns_failure_when_summary_is_empty_string(self):
        fake = FakeChatCompletions([text_response("")])
        es_opts = make_episode_summarization_options(token_threshold=1)
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        result = cap.summarize_episode(conv, force=True)
        assert isinstance(result, Failure)

    def test_warns_but_succeeds_when_model_returns_tool_calls(self):
        fake = FakeChatCompletions(
            [
                tool_call_response("some_tool", {}, "call_1"),
                # The summarization code checks tool_calls but still uses content
                # We need a response with both tool_calls AND content
            ]
        )
        # Actually, the code checks tool_calls and logs a warning, but still
        # proceeds if there's content. Let me create a response with both.
        fake = FakeChatCompletions(
            [
                AssistantMessage(
                    content=[TextChunk(text="A summary.")],
                    tool_calls=[
                        ToolCall(
                            id="call_1",
                            function=FunctionCall(name="unexpected_tool", arguments={}),
                        )
                    ],
                )
            ]
        )
        es_opts = make_episode_summarization_options(token_threshold=1)
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        result = cap.summarize_episode(conv, force=True)
        # Should still succeed despite tool calls (just logs warning)
        assert isinstance(result, Success)


# ---------------------------------------------------------------------------
# Tests: condense_thoughts
# ---------------------------------------------------------------------------


class TestCondenseThoughts:
    def test_returns_none_without_thought_condensation_config(self):
        fake = FakeChatCompletions([text_response("condensed")])
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=None),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = make_conversation()
        result = cap.condense_thoughts(conv, force=True)
        assert result is None

    def test_returns_success_none_when_no_last_turn(self):
        fake = FakeChatCompletions([text_response("condensed")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()  # empty
        result = cap.condense_thoughts(conv, force=True)
        assert isinstance(result, Success)
        assert result.unwrap() is None

    def test_returns_success_none_when_no_content(self):
        fake = FakeChatCompletions([text_response("condensed")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        # Add a turn with no content
        conv.add_turn(
            Turn(
                user_message=UserConversationMessage(
                    message=UserMessage.create("hi"),
                    name="user",
                ),
                assistant_response=AssistantConversationMessage(
                    message=AssistantMessage(content=None),
                    name="assistant",
                    usage=make_usage(),
                ),
            )
        )
        result = cap.condense_thoughts(conv, force=True)
        assert isinstance(result, Success)
        assert result.unwrap() is None

    def test_returns_none_when_below_threshold_not_forced(self):
        fake = FakeChatCompletions([text_response("condensed")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=1000,  # high threshold
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        # Short thoughts (less than 1000 tokens)
        conv.add_turn(make_thought_turn(thoughts="short thought"))
        result = cap.condense_thoughts(conv, force=False)
        assert result is None
        assert len(fake.calls) == 0

    def test_runs_when_forced_even_below_threshold(self):
        fake = FakeChatCompletions([text_response("condensed")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=10000,  # very high
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        conv.add_turn(make_thought_turn(thoughts="short thought"))
        result = cap.condense_thoughts(conv, force=True)
        assert isinstance(result, Success)
        assert result.unwrap() == "condensed"
        assert len(fake.calls) == 1

    def test_extracts_thoughts_from_think_chunks(self):
        fake = FakeChatCompletions([text_response("condensed")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        conv.add_turn(make_thought_turn(thoughts="my detailed thoughts"))
        cap.condense_thoughts(conv, force=True)
        # The thoughts should be sent as user message content
        sent_msg = fake.calls[0]["messages"][0]
        assert isinstance(sent_msg, UserMessage)
        assert message_text(sent_msg) == "my detailed thoughts"

    def test_uses_prompt_as_system_message(self):
        fake = FakeChatCompletions([text_response("condensed")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="CUSTOM CONDENSATION PROMPT",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        conv.add_turn(make_thought_turn())
        cap.condense_thoughts(conv, force=True)
        system_text = message_text(fake.calls[0]["system_message"])
        assert system_text == "CUSTOM CONDENSATION PROMPT"

    def test_uses_correct_model(self):
        fake = FakeChatCompletions([text_response("condensed")])
        tc_opts = ThoughtCondensationOptions(
            model="thought-model",
            prompt="Condense",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        conv.add_turn(make_thought_turn())
        cap.condense_thoughts(conv, force=True)
        assert fake.calls[0]["model"] == "thought-model"

    def test_no_tools_offered(self):
        fake = FakeChatCompletions([text_response("condensed")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        conv.add_turn(make_thought_turn())
        cap.condense_thoughts(conv, force=True)
        assert fake.calls[0]["tools"] == []

    def test_sets_condensed_thoughts_on_message(self):
        fake = FakeChatCompletions([text_response("short version")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        conv.add_turn(make_thought_turn(thoughts="very long thoughts here"))
        cap.condense_thoughts(conv, force=True)
        last_turn = conv.last_episode.last_turn
        assert last_turn.assistant_response.condensed_thoughts == "short version"

    def test_updates_usage_tokens(self):
        fake = FakeChatCompletions([text_response("short")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        original_usage = make_usage(total_tokens=100, completion_tokens=40)
        conv.add_turn(make_thought_turn(thoughts="long thoughts", usage=original_usage))
        cap.condense_thoughts(conv, force=True)
        last_turn = conv.last_episode.last_turn
        # "long thoughts" is 13 chars, "short" is 5 chars
        # compression_ratio = 5 / 13 ≈ 0.3846
        # new_completion_tokens = int(40 * 5/13) = int(15.38...) = 15
        # new_total = 100 - 40 + 15 = 75
        assert last_turn.assistant_response.usage.completion_tokens == 15
        assert last_turn.assistant_response.usage.total_tokens == 75

    def test_returns_failure_when_model_returns_no_content(self):
        fake = FakeChatCompletions([AssistantMessage(content=None)])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        conv.add_turn(make_thought_turn())
        result = cap.condense_thoughts(conv, force=True)
        assert isinstance(result, Failure)

    def test_multiple_think_chunks_all_extracted(self):
        fake = FakeChatCompletions([text_response("condensed")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        conv.add_turn(
            Turn(
                user_message=UserConversationMessage(
                    message=UserMessage.create("question"),
                    name="user",
                ),
                assistant_response=AssistantConversationMessage(
                    message=AssistantMessage(
                        content=[
                            ThinkChunk(thinking=[TextChunk(text="first thought ")]),
                            ThinkChunk(thinking=[TextChunk(text="second thought")]),
                            TextChunk(text="answer"),
                        ]
                    ),
                    name="assistant",
                    usage=make_usage(),
                ),
            )
        )
        cap.condense_thoughts(conv, force=True)
        sent_msg = fake.calls[0]["messages"][0]
        assert message_text(sent_msg) == "first thought second thought"

    def test_ignores_non_text_chunks_in_think_chunks(self):
        from bond.conversation.types import ReferenceChunk

        fake = FakeChatCompletions([text_response("condensed")])
        tc_opts = ThoughtCondensationOptions(
            model="model",
            prompt="Condense",
            token_threshold=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(thought_condensation=tc_opts),
            chat_completions=fake,
            message_list_builder=RecordingMessageListBuilder(),
        )
        conv = Conversation()
        conv.add_turn(
            Turn(
                user_message=UserConversationMessage(
                    message=UserMessage.create("question"),
                    name="user",
                ),
                assistant_response=AssistantConversationMessage(
                    message=AssistantMessage(
                        content=[
                            ThinkChunk(
                                thinking=[
                                    TextChunk(text="text thought"),
                                    ReferenceChunk(reference_ids=[1, 2, 3]),
                                ]
                            ),
                            TextChunk(text="answer"),
                        ]
                    ),
                    name="assistant",
                    usage=make_usage(),
                ),
            )
        )
        cap.condense_thoughts(conv, force=True)
        sent_msg = fake.calls[0]["messages"][0]
        # Only TextChunk content should be extracted
        assert message_text(sent_msg) == "text thought"


# ---------------------------------------------------------------------------
# Tests: Integration with DefaultMessageListBuilder
# ---------------------------------------------------------------------------


class TestDefaultMessageListBuilderIntegration:
    def test_works_with_default_builder(self):
        fake = FakeChatCompletions([text_response("A summary.")])
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            keep_turns=1,
            summary_handler=make_summary_handler(prompt="You are a helpful assistant."),
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=DefaultMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        result = cap.summarize_episode(conv, force=True)
        assert isinstance(result, Success)
        # System message should contain the prompt
        system_text = message_text(fake.calls[0]["system_message"])
        assert "You are a helpful assistant." in system_text

    def test_message_list_includes_conversation_history(self):
        fake = FakeChatCompletions([text_response("A summary.")])
        es_opts = make_episode_summarization_options(
            token_threshold=1,
            keep_turns=1,
        )
        cap = DefaultSummarizationCapability(
            config=make_config(episode_summarization=es_opts),
            chat_completions=fake,
            message_list_builder=DefaultMessageListBuilder(),
        )
        conv = make_conversation(n_turns=3)
        cap.summarize_episode(conv, force=True)
        messages = fake.calls[0]["messages"]
        # Should have messages from the conversation (2 summarized turns) + instruction
        # The exact count depends on the builder, but should include user/assistant messages
        user_msgs = [m for m in messages if isinstance(m, UserMessage)]
        assert len(user_msgs) >= 2  # at least the instruction + some history
