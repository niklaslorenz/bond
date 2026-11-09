"""Regression test: AsyncAgentLoop refreshes ToolCallContext.cwd before each turn.

Without the refresh, a `:cd` (or any other chdir) would leave the tools
operating in the stale directory captured when the loop was created.
"""

import asyncio
import os
from pathlib import Path
from unittest.mock import MagicMock

from returns.result import Success

from bond.behaviours.async_loop import AsyncAgentLoop
from bond.conversation.conversation import Conversation
from bond.conversation.types import UserConversationMessage, UserMessage
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import Toolbox


def _make_loop() -> tuple[AsyncAgentLoop, ToolCallContext, list[Path]]:
    runtime = MagicMock()
    persona = MagicMock()
    persona.toolsets = []
    persona.available_skills = []
    persona.build_toolbox.return_value = Toolbox([])
    persona_config = MagicMock()
    persona_config.instantiate.return_value = persona
    runtime.get_persona.return_value = Success(persona_config)

    recorded: list[Path] = []
    context = ToolCallContext(
        persona=None,
        stdout=None,
        stdin=None,
        is_interactive=False,
        cwd=Path("/stale/initial/cwd"),
        logger=None,
        confirmation_prompt=None,
        conversation=None,
    )
    loop = AsyncAgentLoop(
        runtime=runtime,
        conversation=Conversation(),
        tool_call_context=context,
        event_queue=asyncio.Queue(),
        event_loop=asyncio.get_event_loop(),
        default_persona_id="p",
        stream=False,
        allow_shell_executions=False,
        save_after_turn=False,
        stop_on_failure=True,
    )

    async def fake_run(conversation, signal, tools):
        # capture the cwd the tools would see at turn start
        recorded.append(context.cwd)
        turn = MagicMock()
        turn.assistant_response.message.tool_calls = None
        return Success(turn)

    loop._agent_turn.run = fake_run  # type: ignore[method-assign]
    return loop, context, recorded


def test_cwd_refreshed_before_each_turn(tmp_path: Path, monkeypatch):
    async def scenario():
        loop, context, recorded = _make_loop()
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        await loop.start()
        try:
            monkeypatch.chdir(dir_a)
            loop.prompt(
                UserConversationMessage(message=UserMessage.create("hi"), name="User")
            )
            while len(recorded) < 1:
                await asyncio.sleep(0.01)

            monkeypatch.chdir(dir_b)
            loop.prompt(
                UserConversationMessage(message=UserMessage.create("hi"), name="User")
            )
            while len(recorded) < 2:
                await asyncio.sleep(0.01)
        finally:
            await loop.stop()

        assert recorded == [dir_a, dir_b]
        assert context.cwd == dir_b
        assert context.cwd == Path(os.getcwd())

    asyncio.run(scenario())
