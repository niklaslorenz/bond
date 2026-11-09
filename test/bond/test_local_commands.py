"""Tests for the lsave/lload guards in the CLI and TUI command handlers."""

import asyncio
from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from bond.cli._interactive import _CommandHandler
from bond.conversation.conversation import Conversation
from bond.tui.command_handler import TuiCommandHandler


def _cli_handler(tmp_path: Path, local_path: Path | None):
    runtime = MagicMock()
    runtime.get_local_conversations_path.return_value = local_path
    runtime.get_conversations_path.return_value = tmp_path / "conv"
    loop = MagicMock()
    loop.conversation = Conversation()
    handler = _CommandHandler(runtime, loop, tmp_path / "conv", False)
    return handler, runtime, loop


class TestCliLsaveLload:
    def test_lsave_without_bond_dir_fails(self, tmp_path: Path, capsys):
        handler, _, _ = _cli_handler(tmp_path, None)
        asyncio.run(handler.cmd_lsave(Namespace(name=None)))
        assert "can't be done without a `.bond`" in capsys.readouterr().out

    def test_lsave_without_name_fails(self, tmp_path: Path, capsys):
        local_path = tmp_path / ".bond" / "conversations"
        local_path.mkdir(parents=True)
        handler, _, loop = _cli_handler(tmp_path, local_path)
        conv = loop.conversation
        asyncio.run(handler.cmd_lsave(Namespace(name=None)))
        assert "Please specify a name" in capsys.readouterr().out
        assert conv.name is None

    def test_lsave_with_name_saves_into_local_dir(self, tmp_path: Path, capsys):
        local_path = tmp_path / ".bond" / "conversations"
        local_path.mkdir(parents=True)
        handler, _, loop = _cli_handler(tmp_path, local_path)
        conv = loop.conversation
        asyncio.run(handler.cmd_lsave(Namespace(name="my-conv")))
        assert conv.name == "my-conv"
        assert (local_path / "my-conv_metadata.json").is_file()
        assert (local_path / "my-conv_episodes.json").is_file()

    def test_lload_without_bond_dir_fails(self, tmp_path: Path, capsys):
        handler, _, _ = _cli_handler(tmp_path, None)
        asyncio.run(handler.cmd_lload(Namespace(name="x")))
        assert "can't be done without a `.bond`" in capsys.readouterr().out

    def test_lload_without_name_fails(self, tmp_path: Path, capsys):
        local_path = tmp_path / ".bond" / "conversations"
        local_path.mkdir(parents=True)
        handler, _, _ = _cli_handler(tmp_path, local_path)
        asyncio.run(handler.cmd_lload(Namespace(name=None)))
        assert "Please specify a name" in capsys.readouterr().out

    def test_lload_existing_conversation(self, tmp_path: Path, capsys):
        local_path = tmp_path / ".bond" / "conversations"
        local_path.mkdir(parents=True)
        Conversation(name="x").save_as("x", local_path)
        handler, _, loop = _cli_handler(tmp_path, local_path)
        loop.set_conversation = AsyncMock()
        asyncio.run(handler.cmd_lload(Namespace(name="x")))
        loop.set_conversation.assert_awaited_once()
        assert "Loaded local 'x'" in capsys.readouterr().out


class _FakePause:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeApp:
    def __init__(self, conv: Conversation):
        self.current_conversation = conv
        self.is_idle = True
        self.agent_loop = MagicMock()
        self.agent_loop.pause = lambda: _FakePause()
        self.agent_loop.set_conversation = AsyncMock()
        self.notifications: list[str] = []
        self.chat_view = MagicMock()
        self.chat_view.sync = AsyncMock()
        self.status_bar = MagicMock()
        self.status_bar.set_persona = MagicMock()

    def notify(self, text: str, markup: bool = False, severity: str = "information"):
        self.notifications.append(text)


class TestTuiLsaveLload:
    @pytest.fixture
    def app(self):
        return _FakeApp(Conversation())

    def _handler(self, app, tmp_path: Path, local_path: Path | None):
        runtime = MagicMock()
        runtime.get_local_conversations_path.return_value = local_path
        runtime.get_conversations_path.return_value = tmp_path / "conv"
        runtime.get_cache_path.return_value = tmp_path / "cache"
        return TuiCommandHandler(app, False, runtime)

    def test_lsave_without_bond_dir_fails(self, tmp_path: Path, app):
        handler = self._handler(app, tmp_path, None)
        asyncio.run(handler.lsave(Namespace(name=None)))
        assert "can't be done without a `.bond`" in app.notifications[-1]

    def test_lsave_without_name_fails(self, tmp_path: Path, app):
        local_path = tmp_path / ".bond" / "conversations"
        local_path.mkdir(parents=True)
        handler = self._handler(app, tmp_path, local_path)
        conv = app.current_conversation
        asyncio.run(handler.lsave(Namespace(name=None)))
        assert "Please specify a name" in app.notifications[-1]
        assert conv.name is None

    def test_lsave_with_name_saves_into_local_dir(self, tmp_path: Path, app):
        local_path = tmp_path / ".bond" / "conversations"
        local_path.mkdir(parents=True)
        handler = self._handler(app, tmp_path, local_path)
        conv = app.current_conversation
        asyncio.run(handler.lsave(Namespace(name="my-conv")))
        assert conv.name == "my-conv"
        assert (local_path / "my-conv_metadata.json").is_file()
        assert (local_path / "my-conv_episodes.json").is_file()

    def test_lload_without_bond_dir_fails(self, tmp_path: Path, app):
        handler = self._handler(app, tmp_path, None)
        asyncio.run(handler.lload(Namespace(name="x")))
        assert "can't be done without a `.bond`" in app.notifications[-1]

    def test_lload_existing_conversation(self, tmp_path: Path, app):
        local_path = tmp_path / ".bond" / "conversations"
        local_path.mkdir(parents=True)
        Conversation(name="x").save_as("x", local_path)
        handler = self._handler(app, tmp_path, local_path)
        asyncio.run(handler.lload(Namespace(name="x")))
        app.agent_loop.set_conversation.assert_awaited_once()
        loaded = app.agent_loop.set_conversation.await_args.args[0]
        assert loaded.name == "x"