"""Tests for AsyncAgentLoop state reconciliation (_reconcile_state).

The loop is constructed with a mocked runtime (personas/skills) and a real
Conversation, ToolCallContext, event queue and (not started) event loop.
"""

import asyncio
import logging
from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from returns.result import Failure, Success

from bond.behaviours.async_loop import AsyncAgentLoop
from bond.conversation.conversation import Conversation
from bond.persona import Persona
from bond.skill import Skill
from bond.tools import tool
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import PythonToolset, Toolbox


def run(coro) -> None:
    asyncio.run(coro)


def make_tool(name: str):
    @tool.tool(name=name, description="dummy tool", parameters={}, required=[])
    def t(context):
        return "ok"

    return t


def make_persona(name: str, available_skills: list[str] | None = None):
    runtime = MagicMock()
    runtime.build_toolbox = lambda names: Toolbox([PythonToolset(n, []) for n in names])
    config = MagicMock()
    config.available_skills = list(available_skills or [])
    return Persona(
        name=name,
        config=config,
        generation=MagicMock(),
        summarization=None,
        thought_condensation=None,
        tts=None,
        memory=MagicMock(),
        toolsets=[],
        runtime=runtime,
    )


def make_skill(name: str, tool_name: str) -> Skill:
    skill = Skill(name=name, description="d", instructions="i")
    skill._toolsets = [PythonToolset(f"{name}-tools", [make_tool(tool_name)])]
    return skill


def make_runtime(
    personas: dict[str, Persona], skills: dict[str, Skill] | None = None
) -> MagicMock:
    runtime = MagicMock()

    def get_persona(name: str):
        if name in personas:
            config = MagicMock()
            config.instantiate = lambda: personas[name]
            return Success(config)
        return Failure(f"Unknown persona: {name}")

    def get_skill(name: str):
        if skills and name in skills:
            return Success(skills[name])
        return Failure(f"Unknown skill: {name}")

    runtime.get_persona = get_persona
    runtime.get_skill = get_skill
    return runtime


@pytest.fixture
def make_loop() -> Callable[..., tuple[AsyncAgentLoop, ToolCallContext, asyncio.Queue]]:
    event_loops: list[asyncio.AbstractEventLoop] = []

    def factory(
        runtime, conversation: Conversation, default_persona_id: str = "default"
    ):
        event_loop = asyncio.new_event_loop()
        event_loops.append(event_loop)
        event_queue: asyncio.Queue = asyncio.Queue()
        context = ToolCallContext(None, None, None, False, None, None)
        loop = AsyncAgentLoop(
            runtime,
            conversation,
            context,
            event_queue,
            event_loop,
            default_persona_id,
            stream=False,
            allow_shell_executions=False,
            save_after_turn=False,
            stop_on_failure=False,
        )
        return loop, context, event_queue

    yield factory
    for event_loop in event_loops:
        event_loop.close()


class TestReconcileInit:
    def test_default_persona_derived_and_written_back(self, make_loop):
        p = make_persona("default")
        runtime = make_runtime({"default": p})
        conversation = Conversation()
        assert conversation.persona is None

        loop, context, _ = make_loop(runtime, conversation)

        assert loop.persona is p
        assert conversation.persona == "default"  # explicit write-back
        assert context.persona is p
        assert context.conversation is conversation

    def test_conversation_persona_wins(self, make_loop):
        p_default = make_persona("default")
        p_other = make_persona("other")
        runtime = make_runtime({"default": p_default, "other": p_other})
        conversation = Conversation(persona="other")

        loop, _, _ = make_loop(runtime, conversation)

        assert loop.persona is p_other
        assert conversation.persona == "other"

    def test_invalid_persona_raises_and_emits_error_event(self, make_loop):
        runtime = make_runtime({})  # no personas at all
        conversation = Conversation()
        with pytest.raises(RuntimeError, match="Invalid persona config"):
            make_loop(runtime, conversation)

    def test_reconcile_is_idempotent(self, make_loop):
        p = make_persona("default")
        runtime = make_runtime({"default": p})
        conversation = Conversation()
        loop, _, _ = make_loop(runtime, conversation)

        turn = loop._agent_turn
        toolbox = loop._persona_toolbox
        loop._reconcile_state()
        loop._reconcile_state()

        assert loop._agent_turn is turn  # no rebuild
        assert loop._persona_toolbox is toolbox
        assert not p.memory.release.called


class TestSkillToolsetReconciliation:
    def test_stale_active_skill_is_ignored_not_pruned(self, make_loop, caplog):
        p = make_persona("default", available_skills=[])
        s1 = make_skill("s1", "s1_tool")
        runtime = make_runtime({"default": p}, {"s1": s1})
        conversation = Conversation(
            available_skills=["s1"], active_skills=["s1", "stale"]
        )

        with caplog.at_level(logging.WARNING):
            loop, _, _ = make_loop(runtime, conversation)

        # conversation is not mutated...
        assert conversation.active_skills == ["s1", "stale"]
        # ...but only the effective skill got its toolset loaded
        assert loop._skill_toolbox.has_tool("s1_tool")
        assert set(loop._loaded_skill_toolsets) == {"s1"}
        assert "stale" in caplog.text

    def test_persona_available_skills_used_when_conversation_has_none(self, make_loop):
        p = make_persona("default", available_skills=["s1"])
        s1 = make_skill("s1", "s1_tool")
        runtime = make_runtime({"default": p}, {"s1": s1})
        conversation = Conversation(active_skills=["s1"])

        loop, _, _ = make_loop(runtime, conversation)

        assert loop._skill_toolbox.has_tool("s1_tool")

    def test_reconcile_loads_and_unloads_on_active_skills_change(self, make_loop):
        p = make_persona("default")
        s1 = make_skill("s1", "s1_tool")
        s2 = make_skill("s2", "s2_tool")
        runtime = make_runtime({"default": p}, {"s1": s1, "s2": s2})
        conversation = Conversation(available_skills=["s1", "s2"], active_skills=["s1"])

        loop, _, _ = make_loop(runtime, conversation)
        assert loop._skill_toolbox.has_tool("s1_tool")
        assert not loop._skill_toolbox.has_tool("s2_tool")

        conversation.active_skills.append("s2")
        loop._reconcile_state()
        assert loop._skill_toolbox.has_tool("s1_tool")
        assert loop._skill_toolbox.has_tool("s2_tool")
        assert set(loop._loaded_skill_toolsets) == {"s1", "s2"}

        conversation.active_skills.remove("s1")
        loop._reconcile_state()
        assert not loop._skill_toolbox.has_tool("s1_tool")
        assert loop._skill_toolbox.has_tool("s2_tool")
        assert set(loop._loaded_skill_toolsets) == {"s2"}
        # still no mutation of the conversation
        assert conversation.active_skills == ["s2"]

    def test_unknown_active_skill_does_not_crash(self, make_loop, caplog):
        p = make_persona("default")
        runtime = make_runtime({"default": p}, {})
        conversation = Conversation(available_skills=["ghost"], active_skills=["ghost"])

        with caplog.at_level(logging.WARNING):
            loop, _, _ = make_loop(runtime, conversation)

        assert set(loop._loaded_skill_toolsets) == set()
        assert "ghost" in caplog.text


class TestPersonaAndConversationSwitching:
    def test_set_persona_rebuilds_releases_and_syncs_context(self, make_loop):
        p1 = make_persona("default")
        p2 = make_persona("other")
        runtime = make_runtime({"default": p1, "other": p2})
        conversation = Conversation()
        loop, context, _ = make_loop(runtime, conversation)

        old_toolbox = loop._persona_toolbox
        old_toolbox.release = MagicMock()  # type: ignore[method-assign]
        old_turn = loop._agent_turn

        async def scenario():
            await loop.set_persona("other")

        run(scenario())

        assert loop.persona is p2
        assert conversation.persona == "other"
        assert loop._persona_toolbox is not old_toolbox
        assert loop._agent_turn is not old_turn
        assert p1.memory.release.called  # old persona released
        assert old_toolbox.release.called  # old persona toolbox released
        assert context.persona is p2  # tool call context re-synced

    def test_set_persona_same_id_does_not_rebuild(self, make_loop):
        p1 = make_persona("default")
        p2 = make_persona("other")
        runtime = make_runtime({"default": p1, "other": p2})
        conversation = Conversation()
        loop, _, _ = make_loop(runtime, conversation)

        async def scenario():
            await loop.set_persona("other")
            await loop.set_persona("other")  # same id -> no rebuild

        run(scenario())
        assert loop.persona is p2
        assert not p2.memory.release.called

    def test_set_conversation_reconciles_skill_toolsets_by_content(self, make_loop):
        p = make_persona("default")
        s1 = make_skill("s1", "s1_tool")
        s2 = make_skill("s2", "s2_tool")
        runtime = make_runtime({"default": p}, {"s1": s1, "s2": s2})
        conv1 = Conversation(
            persona="default", available_skills=["s1"], active_skills=["s1"]
        )
        conv2 = Conversation(available_skills=["s2"], active_skills=["s2"])

        loop, context, _ = make_loop(runtime, conv1)
        assert loop._skill_toolbox.has_tool("s1_tool")

        async def scenario():
            await loop.set_conversation(conv2)

        run(scenario())

        assert loop.conversation is conv2
        assert conv2.persona == "default"  # write-back on the new conversation
        assert not loop._skill_toolbox.has_tool(
            "s1_tool"
        )  # old conversation's skill gone
        assert loop._skill_toolbox.has_tool("s2_tool")
        assert set(loop._loaded_skill_toolsets) == {"s2"}
        assert context.conversation is conv2


class TestGuardsAndRelease:

    def test_release_releases_both_toolboxes(self, make_loop):
        p = make_persona("default")
        s1 = make_skill("s1", "s1_tool")
        runtime = make_runtime({"default": p}, {"s1": s1})
        conversation = Conversation(available_skills=["s1"], active_skills=["s1"])
        loop, _, _ = make_loop(runtime, conversation)

        persona_toolbox = loop._persona_toolbox
        persona_toolbox.release = MagicMock()  # type: ignore[method-assign]
        loop._skill_toolbox.release = MagicMock()  # type: ignore[method-assign]

        loop.release()

        persona_toolbox.release.assert_called_once()
        loop._skill_toolbox.release.assert_called_once()


class TestAvailableTools:
    def test_persona_and_skill_tools_combined(self, make_loop):
        base_tool = make_tool("base_tool")
        persona_runtime = MagicMock()
        persona_runtime.build_toolbox = lambda names: Toolbox(
            [PythonToolset("base", [base_tool])]
        )
        config = MagicMock()
        config.available_skills = []
        p = Persona(
            name="default",
            config=config,
            generation=MagicMock(),
            summarization=None,
            thought_condensation=None,
            tts=None,
            memory=MagicMock(),
            toolsets=["base"],
            runtime=persona_runtime,
        )
        s1 = make_skill("s1", "s1_tool")
        runtime = make_runtime({"default": p}, {"s1": s1})
        conversation = Conversation(available_skills=["s1"], active_skills=["s1"])

        loop, _, _ = make_loop(runtime, conversation)

        names = {t.function.name for t in loop._get_available_tools()}
        assert names == {"base_tool", "s1_tool"}
