import os
import shlex
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from bond.behaviours.loop import LoopBehaviour
from bond.conversation.conversation import Conversation
from bond.conversation.types import (AssistantMessage, SystemMessage,
                                     TextChunk, UserMessage)


class DefaultCommandHandler:
    beh: LoopBehaviour

    def __init__(
        self,
        conversation_base_path: Path,
        last_conv_path: Path,
        available_personas: list[str],
        save_on_quit: bool = False,
    ):
        self.conversation_base_path = conversation_base_path
        self.last_conv_path = last_conv_path
        self.available_personas = available_personas
        self.save_on_quit = save_on_quit

        self.parser = ArgumentParser(exit_on_error=False)
        _build_parser(self, self.parser)

    def link(self, beh: LoopBehaviour):
        self.beh = beh
        for name in self.available_personas:
            if name not in beh.env.list_personas():
                raise ValueError(
                    f"The persona '{name}' is not available in the environment"
                )

    def __call__(self, cmd: str):
        self._handle_cmd(cmd)

    def quit(self, _: Namespace) -> None:
        if self.beh.conversation.name is not None:
            self._save_conversation(self.beh.conversation.name)
        if self.save_on_quit:
            print("Save last conversation")
            self._save_last_conversation()
        self.beh.running = False

    def save(self, args: Namespace) -> None:
        name: str | None = args.name or self.beh.conversation.name
        if name is None:
            self.println("<Please specify a name for the conversation>")
            return
        self._save_conversation(name)

    def load(self, args: Namespace) -> None:
        name: str = args.name
        path = self.conversation_base_path / (name + ".json")
        if not path.is_file():
            self.println(f"<Error: unknown conversation name: {name}>")
            return
        self.beh.conversation = Conversation.model_validate_json(path.read_text())
        self.println(
            f"<loaded '{name}' with {len(self.beh.conversation.history)} messages>"
        )

    def new(self, _: Namespace) -> None:
        self.beh.conversation = Conversation()
        self.println("\n\n\n<New Conversation>\n")

    def help(self, _: Namespace) -> None:
        self.println(self.parser.format_help())

    def forget(self, _: Namespace) -> None:
        self.beh.running = False

    def remember(self, _: Namespace) -> None:
        if self.beh.conversation.name is not None:
            self._save_conversation(self.beh.conversation.name)
        self._save_last_conversation()
        self.beh.running = False

    def export(self, _: Namespace) -> None:
        # TODO: implement
        self.println("<Not implemented>")

    def len(self, _: Namespace) -> None:
        self.println(f"<{len(self.beh.conversation.history)} messages>")

    def last(self, args: Namespace) -> None:
        n: int = args.n
        messages = self.beh.conversation.history[-n:]
        for message in messages:
            msg = message.message
            if (
                isinstance(msg, AssistantMessage)
                or isinstance(msg, UserMessage)
                or isinstance(msg, SystemMessage)
            ) and msg.content is not None:
                self.println(f"{message.author}:")
                for chunk in msg.content:
                    if isinstance(chunk, TextChunk):
                        self.print(chunk.text)
                self.println("\n")

    def crop(self, args: Namespace) -> None:
        keep = args.keep
        if keep < 0:
            self.println(
                "<Please specify a positive number for how many messages to keep>"
            )
            return
        self.beh.conversation.history = self.beh.conversation.history[-keep:]
        self.println(f"<Cropped conversation to the last {keep} messages>")

    def who(self, _: Namespace) -> None:
        self.println("<Available Personas:>")
        for persona in self.available_personas:
            self.println(f"  {persona}")

    def to(self, args: Namespace) -> None:
        persona_name: str = args.name
        if persona_name not in self.beh.env.list_personas():
            self.println(f"<'{persona_name}' is not a valid persona>")
            return
        self.beh.set_persona(persona_name)

    def handle_shell_command(self, cmd: str) -> None:
        args = shlex.split(cmd)
        if len(args) == 0:
            self.println("<No command specified>")
            return
        if args[0] == "cd":
            if len(args) != 2:
                self.println("<usage: cd PATH>")
                return
            try:
                os.chdir(args[1])
            except Exception as e:
                self.println(f"{e}")
            self.println(f"cwd: {os.getcwd()}")
        else:
            subprocess.run(
                cmd,
                text=True,
                shell=True,
                check=True,
                stderr=sys.stderr,
                stdout=sys.stdout,
                stdin=sys.stdin,
            )

    def println(self, text: str):
        self.beh.notifier(text + "\n")

    def print(self, text: str):
        self.beh.notifier(text)

    def _save_last_conversation(self):
        self.last_conv_path.write_text(
            self.beh.conversation.model_dump_json(), encoding="utf-8"
        )

    def _save_conversation(self, name: str):
        path = self.conversation_base_path / (name + ".json")
        self.beh.conversation.name = name
        path.write_text(self.beh.conversation.model_dump_json(), encoding="utf-8")
        self._save_last_conversation()

    def _handle_cmd(self, cmd: str):
        try:
            if cmd.strip().startswith(":"):
                cmd_raw = cmd[1:]
                self.handle_shell_command(cmd_raw)
                return
            else:
                args = self.parser.parse_args(shlex.split(cmd))
                args.callback(args)
        except Exception as e:
            self.println(f"error while executing command '{cmd}' ({type(e)}): {e}")
        except SystemExit:
            pass


def _build_parser(repl: DefaultCommandHandler, parser: ArgumentParser):
    subparsers = parser.add_subparsers()
    quit_parser = subparsers.add_parser(
        "quit", help="Quit", aliases=["q"], exit_on_error=False
    )
    quit_parser.set_defaults(callback=repl.quit)

    save_parser = subparsers.add_parser(
        "save", help="Save the conversation", exit_on_error=False
    )
    save_parser.set_defaults(callback=repl.save)
    save_parser.add_argument(
        "name",
        nargs="?",
        type=str,
        help="The name of the conversation",
    )

    load_parser = subparsers.add_parser(
        "load", help="Load the conversation", exit_on_error=False
    )
    load_parser.set_defaults(callback=repl.load)
    load_parser.add_argument("name", type=str, help="Name of the conversation to load")

    new_parser = subparsers.add_parser(
        "new", help="Create a new conversation", exit_on_error=False
    )
    new_parser.set_defaults(callback=repl.new)

    help_parser = subparsers.add_parser(
        "help", help="Show help", aliases=["h", "?"], exit_on_error=False
    )
    help_parser.set_defaults(callback=repl.help)

    forget_parser = subparsers.add_parser(
        "forget", help="Quit without saving", exit_on_error=False
    )
    forget_parser.set_defaults(callback=repl.forget)

    remember_parser = subparsers.add_parser(
        "remember", help="Save and quit", exit_on_error=False
    )
    remember_parser.set_defaults(callback=repl.remember)

    export_parser = subparsers.add_parser(
        "export", help="Export the conversation as a markdown file", exit_on_error=False
    )
    export_parser.set_defaults(callback=repl.export)

    len_parser = subparsers.add_parser(
        "length",
        help="Print the length of the conversation",
        aliases=["len"],
        exit_on_error=False,
    )
    len_parser.set_defaults(callback=repl.len)

    last_parser = subparsers.add_parser(
        "last", help="Print the last n messages", exit_on_error=False
    )
    last_parser.set_defaults(callback=repl.last)
    last_parser.add_argument(
        "n", nargs="?", type=int, default=1, help="Number of messages to print"
    )

    crop_parser = subparsers.add_parser(
        "crop", help="Crop the conversation to the last n messages", exit_on_error=False
    )
    crop_parser.set_defaults(callback=repl.crop)
    crop_parser.add_argument(
        "keep", nargs=1, type=int, help="How many messages to keep"
    )

    who_parser = subparsers.add_parser(
        "who", help="Print the names of available personas", exit_on_error=False
    )
    who_parser.set_defaults(callback=repl.who)

    to_parser = subparsers.add_parser(
        "talk-to",
        help="Set which persona will answer your requests",
        aliases=["ask", "to", "talk-with", "talk"],
        exit_on_error=False,
    )
    to_parser.set_defaults(callback=repl.to)
    to_parser.add_argument("name", type=str, help="Name of the persona")
