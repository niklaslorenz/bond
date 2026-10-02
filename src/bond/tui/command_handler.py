import asyncio
import logging
import os
import shlex
import subprocess
from argparse import ArgumentParser, Namespace, _SubParsersAction

from returns.result import Failure

from bond.behaviours.async_turn import TYPE_CHECKING
from bond.conversation.conversation import Conversation
from bond.runtime import BondRuntime

if TYPE_CHECKING:
    from bond.tui.app import BondTui

logger = logging.getLogger(__name__)


class TuiCommandHandler:

    def __init__(
        self,
        app: "BondTui",
        runtime: BondRuntime | None = None,
    ):
        self._app = app
        self._runtime = runtime or BondRuntime.get_instance()
        self._conversation_base_path = self._runtime.get_conversations_path()
        cache_path = self._runtime.get_cache_path()
        self._last_conv_path = (
            cache_path / "last-conv.json" if cache_path is not None else None
        )
        self._save_on_quit = self._runtime.behaviour_flags.save_on_quit

        self._parser = ArgumentParser(exit_on_error=False)
        self._subparsers = self._parser.add_subparsers(title="command")
        self._build_parser(self._subparsers)

    async def __call__(self, cmd: str) -> bool:
        return await self.handle(cmd)

    def _save_conversation(self, conversation: Conversation):
        if conversation.name and self._conversation_base_path is not None:
            conversation.save_to_file(
                self._conversation_base_path / (conversation.name + ".json")
            )

    def _save_last_conversation(self, conversation: Conversation):
        if self._last_conv_path is not None:
            conversation.save_to_file(self._last_conv_path)

    # Command Callbacks

    async def quit(self, args: Namespace) -> bool:
        if not args.force and self._app.chat_lock.locked():
            return False
        conversation = self._app.current_conversation
        await self._app.exit()
        if self._save_on_quit:
            async with self._app.chat_lock:
                self._save_conversation(conversation)
                self._save_last_conversation(conversation)
        return True

    async def save(self, args: Namespace) -> bool:
        if self._app.chat_lock.locked():
            return False
        conv = self._app.current_conversation
        name: str | None = args.name or conv.name
        if name is None:
            self._notify("Please specify a name for the conversation")
            return True
        conv.name = name
        async with self._app.chat_lock:
            self._save_conversation(conv)
            if self._save_on_quit:
                self._save_last_conversation(conv)
        self._notify(f"Saved as '{name}'")
        return True

    async def _load_conversation_interactive(self):
        assert self._conversation_base_path is not None
        async with self._app.action_lock:
            result = await self._app.select_conversation(
                self._list_conversations(), True
            )
            logger.debug(f"Selected conversation: {result}")
            if isinstance(result, Failure):
                return False
            name = result.unwrap()
            if name == None:
                return True
            path = self._conversation_base_path / (name + ".json")
            if not path.is_file():
                self._notify(f"Error: unable to find conversation: {name}")
                return True
            await self._app.agent_loop.set_conversation(
                Conversation.load_from_file(path)
            )
            await self._app.chat_view.sync(self._app.current_conversation)
            self._app.chat_view.status_bar.set_persona(
                self._app.agent_loop.persona.name
            )

    async def load(self, args: Namespace) -> bool:
        if self._app.chat_lock.locked():
            return False
        name: str | None = args.name
        if self._conversation_base_path is None:
            self._notify("Conversation loading is not supported")
            return True
        if name is None:
            logger.debug(
                "No name provided for load command. Launching interactive load prompt"
            )
            self._app.schedule(self._load_conversation_interactive())
            return True
        path = self._conversation_base_path / (name + ".json")
        if not path.is_file():
            self._notify(f"Error: unable to find conversation: {name}")
            return True
        await self._app.agent_loop.set_conversation(Conversation.load_from_file(path))
        await self._app.chat_view.sync(self._app.current_conversation)
        self._app.chat_view.status_bar.set_persona(self._app.agent_loop.persona.name)
        return True

    async def new(self, args: Namespace) -> bool:
        if self._app.chat_lock.locked():
            return False
        await self._app.agent_loop.new_conversation(args.to)
        await self._app.chat_view.sync(self._app.current_conversation)
        return True

    async def forget(self, args: Namespace) -> bool:
        if not args.force and self._app.chat_lock.locked():
            return False
        await self._app.exit()
        return True

    async def remember(self, args: Namespace) -> bool:
        if not args.force and self._app.chat_lock.locked():
            return False
        async with self._app.chat_lock:
            conv = self._app.current_conversation
            self._save_conversation(conv)
            self._save_last_conversation(conv)
        await self._app.exit()
        return True

    async def to(self, args: Namespace) -> bool:
        if self._app.chat_lock.locked():
            return False
        persona_name: str = args.name
        if persona_name not in self._runtime.list_personas():
            self._notify(f"'{persona_name}' is not a valid persona")
            return False
        await self._app.agent_loop.set_persona(persona_name)
        self._app.chat_view.status_bar.set_persona(self._app.agent_loop.persona.name)
        return True

    async def delete(self, args: Namespace) -> bool:
        if self._app.chat_lock.locked():
            return False
        n: int = args.n
        if n < 0:
            self._notify(
                "Please specify a positive number for how many turns to delete"
            )
            return True
        async with self._app.chat_lock:
            conversation = self._app.current_conversation
            user_msg_indices = [
                idx
                for (idx, msg) in enumerate(conversation.history)
                if msg.message.role == "user"
            ]
            delete_to = user_msg_indices[-n] if len(user_msg_indices) >= n else -1
            if delete_to >= 0:
                conversation.history = conversation.history[:delete_to]
                conversation.summary_index = max(
                    conversation.summary_index, len(conversation.history)
                )
            else:
                conversation.history = []
                conversation.summary = None
                conversation.summary_index = 0
            await self._app.chat_view.sync(conversation)
        return True

    async def summarize(self, _: Namespace) -> bool:
        if self._app.chat_lock.locked():
            return False
        result = await self._app.agent_loop.summarize()
        if isinstance(result, Failure):
            self._notify(result.failure())
        return True

    # Helper methods

    def _notify(self, text: str):
        self._app.notify(text)

    def _handle_shell_command(
        self, cmd: str, stdin=None, stdout=None, stderr=None
    ) -> None:
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
        else:
            process = subprocess.run(
                cmd,
                text=True,
                shell=True,
                check=True,
                stderr=stderr,
                stdout=stdout,
                stdin=stdin,
            )
            # TODO: Maybe introduce a new popup that can show a longer message
            # and only show one-liners as notification
            self._notify(process.stdout)

    def _list_conversations(self) -> list[str]:
        if (
            self._conversation_base_path is None
            or not self._conversation_base_path.exists()
        ):
            return []
        files = [
            (path.stat().st_mtime if path.exists() else 0.0, path.stem)
            for path in self._conversation_base_path.iterdir()
            if path.is_file() and path.suffix == ".json"
        ]
        files.sort(key=lambda item: item[0], reverse=True)
        return [name for _, name in files]

    async def handle(self, cmd: str) -> bool:
        if self._app.action_lock.locked():
            return False
        async with self._app.action_lock:
            try:
                if cmd.strip().startswith(":"):
                    cmd_raw = cmd[1:]
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._handle_shell_command, cmd_raw, None, subprocess.PIPE
                    )

                    return True
                else:
                    args = self._parser.parse_args(shlex.split(cmd))
                    return await args.callback(args)
            except Exception as e:
                self._notify(f"error while executing command '{cmd}' ({type(e)}): {e}")
        return True

    def _build_parser(self, subparsers: _SubParsersAction):
        quit_parser = subparsers.add_parser(
            "quit", help="Quit", aliases=["q"], exit_on_error=False
        )
        quit_parser.add_argument(
            "--force", "-f", action="store_true", help="Force quit the app"
        )
        quit_parser.set_defaults(callback=self.quit)

        save_parser = subparsers.add_parser(
            "save", help="Save the conversation", exit_on_error=False
        )
        save_parser.set_defaults(callback=self.save)
        save_parser.add_argument(
            "name",
            nargs="?",
            type=str,
            help="The name of the conversation",
        )

        load_parser = subparsers.add_parser(
            "load", help="Load the conversation", exit_on_error=False
        )
        load_parser.set_defaults(callback=self.load)
        load_parser.add_argument(
            "name",
            nargs="?",
            type=str,
            help="Name of the conversation to load",
        )

        new_parser = subparsers.add_parser(
            "new", help="Create a new conversation", exit_on_error=False
        )
        new_parser.add_argument(
            "--to", type=str, help="Persona for the new conversation"
        )
        new_parser.set_defaults(callback=self.new)

        forget_parser = subparsers.add_parser(
            "forget", help="Quit without saving", exit_on_error=False
        )
        forget_parser.add_argument(
            "--force", "-f", action="store_true", help="Force quit the app"
        )
        forget_parser.set_defaults(callback=self.forget)

        remember_parser = subparsers.add_parser(
            "remember", help="Save and quit", exit_on_error=False
        )
        remember_parser.add_argument(
            "--force", "-f", action="store_true", help="Force quit the app"
        )
        remember_parser.set_defaults(callback=self.remember)

        to_parser = subparsers.add_parser(
            "talk-to",
            help="Set which persona will answer your requests",
            aliases=["ask", "to", "talk-with", "talk"],
            exit_on_error=False,
        )
        to_parser.set_defaults(callback=self.to)
        to_parser.add_argument("name", type=str, help="Name of the persona")

        del_parser = subparsers.add_parser(
            "delete",
            help="Delete the last n messages",
            aliases=["del"],
            exit_on_error=False,
        )
        del_parser.set_defaults(callback=self.delete)
        del_parser.add_argument(
            "n", nargs="?", type=int, default=1, help="Number of turns to delete"
        )

        summarize_parser = subparsers.add_parser(
            "summarize",
            help="Create a summary of the conversation",
            aliases=["sum"],
            exit_on_error=False,
        )
        summarize_parser.set_defaults(callback=self.summarize)
