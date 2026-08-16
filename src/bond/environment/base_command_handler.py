import os
import shlex
import subprocess
from argparse import ArgumentParser, Namespace, _SubParsersAction
from pathlib import Path

from bond.behaviours.behaviour_event import (NotifyEvent,
                                             RestoreConversationEvent)
from bond.behaviours.behaviour_signal import StopSignal
from bond.behaviours.loop import LoopBehaviour
from bond.behaviours.types import IBehaviourEventHandler
from bond.conversation.conversation import Conversation
from bond.conversation.types import AssistantMessage
from bond.environment.types import IBehaviourSignalHandler
from bond.runtime import BondRuntime


class BaseCommandHandler:
    beh: LoopBehaviour

    def __init__(
        self,
        event_handler: IBehaviourEventHandler,
        signal_handler: IBehaviourSignalHandler,
        conversation_base_path: Path,
        last_conv_path: Path,
        available_personas: list[str],
        save_on_quit: bool = False,
    ):
        self.event_handler = event_handler
        self.signal_handler = signal_handler
        self.conversation_base_path = conversation_base_path
        self.last_conv_path = last_conv_path
        self.available_personas = available_personas
        self.save_on_quit = save_on_quit

        self.parser = ArgumentParser(exit_on_error=False)
        self.subparsers = self.parser.add_subparsers(title="command")
        self.build_parser(self.subparsers)

    def link(self, beh: LoopBehaviour):
        self.beh = beh
        self.env = BondRuntime.get_instance()
        for name in self.available_personas:
            if name not in self.env.list_personas():
                raise ValueError(
                    f"The persona '{name}' is not available in the environment"
                )

    def __call__(self, cmd: str):
        self.handle_cmd(cmd)

    # Command Callbacks

    def quit(self, _: Namespace) -> None:
        if self.beh.conversation.name is not None:
            self.save_conversation(self.beh.conversation.name)
        if self.save_on_quit:
            self.save_last_conversation()
        self.signal_handler.queue_signal(StopSignal())

    def save(self, args: Namespace) -> None:
        name: str | None = args.name or self.beh.conversation.name
        if name is None:
            self.notify("Please specify a name for the conversation")
            return
        self.save_conversation(name)
        self.notify(f"Saved as '{name}'")

    def clear_tool_calls(self, args: Namespace) -> None:
        for msg in self.beh.conversation.history:
            if (
                isinstance(msg.message, AssistantMessage)
                and msg.message.tool_calls != None
            ):
                msg.message.tool_calls = None
        self.beh.conversation.history = [
            msg
            for msg in self.beh.conversation.history
            if not isinstance(msg.message, AssistantMessage)
            or msg.message.content != None
        ]
        if args.full:
            self.beh.conversation.history = [
                msg
                for msg in self.beh.conversation.history
                if msg.message.role != "tool"
            ]
        self.event_handler(
            RestoreConversationEvent(
                conversation=self.beh.conversation,
            )
        )

    def load(self, args: Namespace) -> None:
        name: str | None = args.name
        if not name:
            self.notify("Please specify a name for the conversation to load")
            return
        path = self.conversation_base_path / (name + ".json")
        if not path.is_file():
            self.notify(f"Error: unknown conversation name: {name}")
            return
        self.beh.set_conversation(Conversation.model_validate_json(path.read_text()))

    def new(self, _: Namespace) -> None:
        self.beh.new_conversation()

    def forget(self, _: Namespace) -> None:
        self.signal_handler.queue_signal(StopSignal())

    def remember(self, _: Namespace) -> None:
        if self.beh.conversation.name is not None:
            self.save_conversation(self.beh.conversation.name)
        self.save_last_conversation()
        self.signal_handler.queue_signal(StopSignal())

    def crop(self, args: Namespace) -> None:
        keep = args.keep
        if keep < 0:
            self.notify("Please specify a positive number for how many turns to keep")
            return
        if keep == 0:
            self.beh.set_conversation(Conversation(current_persona=self.beh.persona_id))
            return

        user_msg_indices = [
            idx
            for (idx, msg) in enumerate(self.beh.conversation.history)
            if msg.message.role == "user"
        ]
        delete_to = user_msg_indices[-keep] if len(user_msg_indices) >= keep else -1
        if delete_to >= 0:
            self.beh.conversation.history = self.beh.conversation.history[delete_to:]
            self.event_handler(
                RestoreConversationEvent(conversation=self.beh.conversation)
            )

    def to(self, args: Namespace) -> None:
        persona_name: str = args.name
        if persona_name not in self.env.list_personas():
            self.notify(f"'{persona_name}' is not a valid persona")
            return
        self.beh.set_persona(persona_name, True)

    def delete(self, args: Namespace) -> None:
        n: int = args.n
        if n < 0:
            self.notify("Please specify a positive number for how many turns to delete")
            return

        user_msg_indices = [
            idx
            for (idx, msg) in enumerate(self.beh.conversation.history)
            if msg.message.role == "user"
        ]
        delete_to = user_msg_indices[-n] if len(user_msg_indices) >= n else -1
        if delete_to >= 0:
            self.beh.conversation.history = self.beh.conversation.history[:delete_to]
        else:
            self.beh.conversation.history = []
        self.event_handler(RestoreConversationEvent(conversation=self.beh.conversation))

    # Helper methods

    def notify(self, text: str):
        self.event_handler(NotifyEvent(message=text))

    def handle_shell_command(
        self, cmd: str, stdin=None, stdout=None, stderr=None
    ) -> None:
        args = shlex.split(cmd)
        if len(args) == 0:
            self.notify("No command specified")
            return
        if args[0] == "cd":
            if len(args) != 2:
                self.notify("usage: cd PATH")
                return
            try:
                os.chdir(args[1])
            except Exception as e:
                self.notify(f"{e}")
            self.notify(f"cwd: {os.getcwd()}")
        else:
            subprocess.run(
                cmd,
                text=True,
                shell=True,
                check=True,
                stderr=stderr,
                stdout=stdout,
                stdin=stdin,
            )

    def save_last_conversation(self):
        self.beh.conversation.save_to_file(self.last_conv_path)

    def save_conversation(self, name: str):
        path = self.conversation_base_path / (name + ".json")
        self.beh.conversation.name = name
        self.beh.conversation.save_to_file(path)
        self.save_last_conversation()

    def list_conversations(self) -> list[str]:
        if not self.conversation_base_path.exists():
            return []
        files = [
            (path.stat().st_mtime if path.exists() else 0.0, path.stem)
            for path in self.conversation_base_path.iterdir()
            if path.is_file() and path.suffix == ".json"
        ]
        files.sort(key=lambda item: item[0], reverse=True)
        return [name for _, name in files]

    def handle_cmd(self, cmd: str):
        try:
            if cmd.strip().startswith(":"):
                cmd_raw = cmd[1:]
                self.handle_shell_command(cmd_raw)
                return
            else:
                args = self.parser.parse_args(shlex.split(cmd))
                args.callback(args)
        except Exception as e:
            self.notify(f"error while executing command '{cmd}' ({type(e)}): {e}")
        except SystemExit:
            pass

    def build_parser(self, subparsers: _SubParsersAction):
        quit_parser = subparsers.add_parser(
            "quit", help="Quit", aliases=["q"], exit_on_error=False
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

        clear_tool_calls_parser = subparsers.add_parser(
            "clear-tools",
            help="Clears tool calls from the conversation",
            exit_on_error=False,
        )
        clear_tool_calls_parser.set_defaults(callback=self.clear_tool_calls)
        clear_tool_calls_parser.add_argument(
            "--full", "-f", action="store_true", help="Clear tool result messages too"
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
        new_parser.set_defaults(callback=self.new)

        forget_parser = subparsers.add_parser(
            "forget", help="Quit without saving", exit_on_error=False
        )
        forget_parser.set_defaults(callback=self.forget)

        remember_parser = subparsers.add_parser(
            "remember", help="Save and quit", exit_on_error=False
        )
        remember_parser.set_defaults(callback=self.remember)

        crop_parser = subparsers.add_parser(
            "crop",
            help="Crop the conversation to the last n messages",
            exit_on_error=False,
        )
        crop_parser.set_defaults(callback=self.crop)
        crop_parser.add_argument("keep", type=int, help="How many turns to keep")

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
