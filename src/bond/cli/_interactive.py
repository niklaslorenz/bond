import asyncio
import os
import shlex
import subprocess
import sys
from argparse import ArgumentParser, Namespace, _SubParsersAction
from pathlib import Path
from typing import Literal

from returns.result import Failure

from bond.behaviours.async_loop import AsyncAgentLoop
from bond.behaviours.async_turn import AsyncTurnEvent
from bond.behaviours.types import LoopStatus
from bond.config import get_default_persona
from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    ConversationMessage,
    TextChunk,
    ThinkChunk,
    UserConversationMessage,
    UserMessage,
)
from bond.environment.std_async_event_handler import StdAsyncEventHandler
from bond.runtime import BondRuntime
from bond.tools.tool import ToolCallContext

from . import logger


def _message_parts(message: ConversationMessage) -> tuple[str | None, str | None]:
    """Split a conversation message into (text, thoughts)."""
    inner = getattr(message, "message", None)
    if inner is None:
        content = getattr(message, "content", None)
        return (content, None) if isinstance(content, str) else (None, None)
    text_parts: list[str] = []
    think_parts: list[str] = []
    for chunk in getattr(inner, "content", None) or []:
        if isinstance(chunk, TextChunk):
            text_parts.append(chunk.text)
        elif isinstance(chunk, ThinkChunk):
            think_parts.append(
                "".join(c.text for c in chunk.thinking if isinstance(c, TextChunk))
            )
    return "".join(text_parts) or None, "".join(think_parts) or None


def _all_messages(conversation: Conversation) -> list[ConversationMessage]:
    messages: list[ConversationMessage] = []
    for episode in conversation.episodes:
        for turn in episode.turns:
            messages.extend(turn.flatten())
    return messages


class _CommandHandler:
    """Handles ':'-prefixed commands in an interactive CLI session.

    Mirrors the command set of the TUI (see src/bond/tui/command_handler.py).
    A second ':' (e.g. '::ls') runs a shell command instead.
    """

    def __init__(
        self,
        runtime: BondRuntime,
        loop: AsyncAgentLoop,
        conv_path: Path,
        conv_name: str,
        show_thoughts: bool,
    ):
        self._runtime = runtime
        self._loop = loop
        self._conv_path = conv_path
        self._conv_name = conv_name
        self._show_thoughts = show_thoughts
        self.save_on_exit = True
        self.quit = False

        self._parser = ArgumentParser(prog=":", exit_on_error=False)
        subparsers = self._parser.add_subparsers(title="command")
        self._build_parser(subparsers)

    def _notify(self, text: str):
        print(text)

    @property
    def _conversations_path(self) -> Path:
        path = self._runtime.get_conversations_path()
        assert path is not None
        return path

    async def _quit(self, save: bool):
        self.save_on_exit = save
        self.quit = True

    # Command callbacks

    async def cmd_quit(self, _: Namespace):
        await self._quit(save=True)

    async def cmd_forget(self, _: Namespace):
        await self._quit(save=False)

    async def cmd_remember(self, _: Namespace):
        await self._quit(save=True)

    async def cmd_save(self, args: Namespace):
        conv = self._loop.conversation
        if args.name is not None:
            conv.move_to(args.name, self._conversations_path)
            self._notify(f"Saved as '{args.name}'")
        else:
            self._conv_path.mkdir(parents=True, exist_ok=True)
            conv.save_as(self._conv_name, self._conv_path)
            self._notify(f"Saved as '{self._conv_name}'")

    async def cmd_load(self, args: Namespace):
        name: str | None = args.name
        if not name:
            self._notify("Please specify a name for the conversation to load")
            return
        if not Conversation.exists(name, self._conversations_path):
            self._notify(f"Error: unknown conversation name: {name}")
            return
        conversation = Conversation.load(name, self._conversations_path)
        await self._loop.set_conversation(conversation)
        n_turns = sum(len(ep.turns) for ep in conversation.episodes)
        self._notify(f"Loaded '{name}' with {n_turns} turns")

    async def cmd_new(self, args: Namespace):
        persona = args.to or self._loop.conversation.persona
        if persona is not None and persona not in self._runtime.list_personas():
            self._notify(f"'{persona}' is not a valid persona")
            return
        await self._loop.set_conversation(Conversation(persona=persona))
        self._notify("<New Conversation>")

    async def cmd_to(self, args: Namespace):
        persona_name: str = args.name
        if persona_name not in self._runtime.list_personas():
            self._notify(f"'{persona_name}' is not a valid persona")
            return
        await self._loop.set_persona(persona_name)
        self._notify(f"Now talking to {self._loop.persona.name}")

    async def cmd_delete(self, args: Namespace):
        n: int = args.n
        if n <= 0:
            self._notify("Please specify a positive number of turns to delete")
            return
        self._loop.conversation.delete_turns(n)
        self._notify(f"Deleted the last {n} turn(s)")

    async def cmd_summarize(self, _: Namespace):
        result = await self._loop.summarize()
        if result is None:
            self._notify("Summarization is not configured for this persona")
        elif isinstance(result, Failure):
            self._notify(result.failure())
        else:
            self._notify(f"Summarized {result.unwrap()} turn(s)")

    async def cmd_length(self, _: Namespace):
        n = sum(len(ep.turns) for ep in self._loop.conversation.episodes)
        self._notify(f"{n} turn(s)")

    async def cmd_last(self, args: Namespace):
        messages = _all_messages(self._loop.conversation)[-args.n :]
        for message in messages:
            author = getattr(message, "name", None) or "assistant"
            print(f"\n{author}:")
            text, think = _message_parts(message)
            if think is not None and self._show_thoughts:
                print(f"[THINK]\n{think}\n[/THINK]")
            if text is not None:
                print(f"{text}\n")

    async def cmd_who(self, _: Namespace):
        personas = self._runtime.list_personas()
        self._notify("Available Personas:\n" + "\n".join(f"  {p}" for p in personas))

    async def cmd_name(self, _: Namespace):
        self._notify(self._loop.conversation.name or "<unnamed>")

    async def cmd_help(self, _: Namespace):
        self._notify(self._parser.format_help())

    async def _handle_shell_command(self, cmd: str):
        args = shlex.split(cmd)
        if len(args) == 0:
            self._notify("No command specified")
            return
        if args[0] == "cd":
            if len(args) != 2:
                self._notify("usage: cd PATH")
                return
            try:
                os.chdir(args[1])
            except Exception as e:
                self._notify(f"{e}")
            self._notify(f"cwd: {os.getcwd()}")
            return
        process = await asyncio.to_thread(
            subprocess.run, cmd, text=True, shell=True, capture_output=True
        )
        output = ((process.stdout or "") + (process.stderr or "")).strip()
        if output:
            self._notify(output)
        if process.returncode != 0:
            self._notify(f"[exit code {process.returncode}]")

    async def handle(self, cmd: str):
        """Handle one command (the leading ':' has already been stripped)."""
        try:
            if cmd.strip().startswith(":"):
                # '::ls' runs the shell command 'ls'
                await self._handle_shell_command(cmd[1:])
                return
            args = self._parser.parse_args(shlex.split(cmd))
            await args.callback(args)
        except SystemExit:
            pass
        except Exception as e:
            self._notify(f"error while executing command '{cmd}' ({type(e)}): {e}")

    def _build_parser(self, subparsers: _SubParsersAction):
        quit_parser = subparsers.add_parser(
            "quit", help="Save and quit", aliases=["q"], exit_on_error=False
        )
        quit_parser.set_defaults(callback=self.cmd_quit)

        forget_parser = subparsers.add_parser(
            "forget", help="Quit without saving", exit_on_error=False
        )
        forget_parser.set_defaults(callback=self.cmd_forget)

        remember_parser = subparsers.add_parser(
            "remember", help="Save and quit", exit_on_error=False
        )
        remember_parser.set_defaults(callback=self.cmd_remember)

        save_parser = subparsers.add_parser(
            "save", help="Save the conversation", exit_on_error=False
        )
        save_parser.set_defaults(callback=self.cmd_save)
        save_parser.add_argument(
            "name", nargs="?", type=str, help="Name to save the conversation under"
        )

        load_parser = subparsers.add_parser(
            "load", help="Load a conversation", exit_on_error=False
        )
        load_parser.set_defaults(callback=self.cmd_load)
        load_parser.add_argument(
            "name", nargs="?", type=str, help="Name of the conversation to load"
        )

        new_parser = subparsers.add_parser(
            "new", help="Start a new conversation", exit_on_error=False
        )
        new_parser.add_argument("--to", type=str, help="Persona for the new one")
        new_parser.set_defaults(callback=self.cmd_new)

        to_parser = subparsers.add_parser(
            "talk-to",
            help="Switch persona",
            aliases=["to", "talk-with", "talk", "ask"],
            exit_on_error=False,
        )
        to_parser.set_defaults(callback=self.cmd_to)
        to_parser.add_argument("name", type=str, help="Name of the persona")

        del_parser = subparsers.add_parser(
            "delete",
            help="Delete the last n turns",
            aliases=["del"],
            exit_on_error=False,
        )
        del_parser.set_defaults(callback=self.cmd_delete)
        del_parser.add_argument(
            "n", nargs="?", type=int, default=1, help="Number of turns to delete"
        )

        sum_parser = subparsers.add_parser(
            "summarize",
            help="Summarize the conversation",
            aliases=["sum"],
            exit_on_error=False,
        )
        sum_parser.set_defaults(callback=self.cmd_summarize)

        len_parser = subparsers.add_parser(
            "length", help="Print the number of turns", aliases=["len"],
            exit_on_error=False,
        )
        len_parser.set_defaults(callback=self.cmd_length)

        last_parser = subparsers.add_parser(
            "last", help="Print the last n messages", exit_on_error=False
        )
        last_parser.set_defaults(callback=self.cmd_last)
        last_parser.add_argument(
            "n", nargs="?", type=int, default=1, help="Number of messages to print"
        )

        who_parser = subparsers.add_parser(
            "who", help="List available personas", exit_on_error=False
        )
        who_parser.set_defaults(callback=self.cmd_who)

        name_parser = subparsers.add_parser(
            "get_name",
            help="Show the conversation name",
            aliases=["name"],
            exit_on_error=False,
        )
        name_parser.set_defaults(callback=self.cmd_name)

        help_parser = subparsers.add_parser(
            "help", help="Show this help", aliases=["h", "?"], exit_on_error=False
        )
        help_parser.set_defaults(callback=self.cmd_help)


async def wait_for_turn_done(loop: AsyncAgentLoop) -> None:
    """Wait until the loop is idle again after a prompt (incl. tool calls)."""
    turn_done = asyncio.Event()
    was_busy = False

    def on_loop_status(status: LoopStatus):
        nonlocal was_busy
        if status == "Idle" and was_busy:
            turn_done.set()
        elif status == "Stopped":
            turn_done.set()
        else:
            was_busy = True

    loop.loop_status.subscribe(on_loop_status)
    try:
        await turn_done.wait()
    finally:
        loop.loop_status.unsubscribe(on_loop_status)


async def run_interactive_session(
    *,
    conv_path: Path,
    env_path: Path,
    conv_name: str,
    config_section: Literal["ask", "chat"],
    show_thoughts: bool,
    show_tool_output: bool,
    stream: bool,
    is_interactive: bool,
    save_after_turn: bool,
    user_name: str = "User",
) -> None:
    """Run an interactive chat session driven by an :class:`AsyncAgentLoop`.

    Loads (or creates) the conversation stored under *conv_name* inside
    *conv_path*, lets the user chat line by line and saves the conversation
    after every turn (if *save_after_turn*) and once more on exit (unless the
    user quits via ':forget'). Lines starting with ':' are handled as
    commands, see :class:`_CommandHandler`.
    """
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic(env_path)
    config = runtime.get_bond_config()
    frontend_config = config.ask if config_section == "ask" else config.chat

    available_personas = runtime.list_personas()

    if Conversation.exists(conv_name, conv_path):
        conversation = Conversation.load(conv_name, conv_path)
    else:
        conversation = Conversation()

    persona_id: str = conversation.persona or get_default_persona(frontend_config)
    if persona_id not in available_personas:
        raise ValueError(
            f"not a valid persona: {persona_id}. "
            f"Available personas: {'\n'.join(available_personas)}"
        )
    persona_config_result = runtime.get_persona(persona_id)
    if isinstance(persona_config_result, Failure):
        print(persona_config_result.failure(), file=sys.stderr)
        return
    allow_shell = "shell" in persona_config_result.unwrap().toolsets

    n_turns = sum(len(episode.turns) for episode in conversation.episodes)
    if n_turns == 0:
        print("<New Conversation>")
    else:
        print(f"<Loaded {n_turns} turns>")

    event_loop = asyncio.get_event_loop()
    event_queue: asyncio.Queue[AsyncTurnEvent] = asyncio.Queue()
    tool_call_context = ToolCallContext.async_default(
        None, is_interactive, conversation, event_loop, event_queue
    )
    event_handler = StdAsyncEventHandler(
        event_queue,
        show_thoughts,
        show_tool_output,
        is_interactive,
        echo_user_message=True,
    )
    loop = AsyncAgentLoop(
        runtime,
        conversation,
        tool_call_context,
        event_queue,
        event_loop,
        persona_id,
        stream=stream,
        allow_shell_executions=allow_shell,
        save_after_turn=False,
        stop_on_failure=False,
    )

    command_handler = _CommandHandler(
        runtime, loop, conv_path, conv_name, show_thoughts
    )

    event_handler.start(event_loop)
    try:
        await loop.start()
        while not command_handler.quit:
            try:
                line = await asyncio.to_thread(input, f"[to {loop.persona.name}] ")
            except EOFError:
                break
            line = line.strip()
            if not line:
                continue
            if line.startswith(":"):
                await command_handler.handle(line[1:])
                continue
            user_message = UserConversationMessage(
                message=UserMessage.create(line), name=user_name
            )
            prompt_result = loop.prompt(user_message)
            if isinstance(prompt_result, Failure):
                print(prompt_result.failure(), file=sys.stderr)
                continue
            await wait_for_turn_done(loop)
            if save_after_turn:
                conv_path.mkdir(parents=True, exist_ok=True)
                loop.conversation.save_as(conv_name, conv_path)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Interrupted by user")
        await loop.cancel()
    finally:
        if loop.is_running:
            await loop.stop()
        # Let the event handler print everything that is still queued up
        await event_handler.drain()
        await event_handler.stop()

    if command_handler.save_on_exit:
        conv_path.mkdir(parents=True, exist_ok=True)
        loop.conversation.save_as(conv_name, conv_path)
    loop.persona.release()
