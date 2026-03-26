import shlex
from argparse import ArgumentParser, Namespace
from pathlib import Path

from bond.behaviours.loop import LoopBehaviour
from bond.conversation.conversation import Conversation
from bond.tools.tool import BidirectionalTextIO


class Repl:

    def __init__(
        self,
        beh: LoopBehaviour,
        conversation: Conversation,
        conversation_base_path: Path,
        last_conv_path: Path,
        user_io: BidirectionalTextIO,
        available_personas: list[str],
        save_on_quit: bool = False,
    ):
        for name in available_personas:
            if name not in beh.env.list_personas():
                raise ValueError(
                    f"The persona '{name}' is not available in the environment"
                )

        self.beh = beh
        self.conversation = conversation
        self.conversation_base_path = conversation_base_path
        self.last_conv_path = last_conv_path
        self.available_personas = available_personas
        self.save_on_quit = save_on_quit
        self.user_io = user_io

        self.parser = ArgumentParser()
        _build_parser(self, self.parser)
        self.beh.command_handler = lambda cmd: _handle_cmd(self.parser, cmd)

    def run(self):
        self.beh.run(self.conversation)

    def quit(self, _: Namespace) -> None:
        if self.conversation.name is not None:
            self._save_conversation(self.conversation.name)
        if self.save_on_quit:
            self._save_last_conversation()
        self.beh.running = False

    def save(self, args: Namespace) -> None:
        name: str | None = args.name or self.conversation.name
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
        self.conversation = Conversation.model_validate_json(path.read_text())
        self.println(
            f"<loaded '{name}' with {len(self.conversation.history)} messages>"
        )

    def new(self, _: Namespace) -> None:
        self.conversation = Conversation()
        self.println("\n\n\n<New Conversation>\n")

    def help(self, _: Namespace) -> None:
        self.parser.print_help(self.user_io.text_out)

    def forget(self, _: Namespace) -> None:
        self.beh.running = False

    def remember(self, _: Namespace) -> None:
        if self.conversation.name is not None:
            self._save_conversation(self.conversation.name)
        self._save_last_conversation()
        self.beh.running = False

    def export(self, _: Namespace) -> None:
        self.println("<Not implemented>")

    def len(self, _: Namespace) -> None:
        self.println(f"<{len(self.conversation.history)} messages>")

    def last(self, _: Namespace) -> None:
        # TODO: implement
        self.println("<Not implemented>")

    def crop(self, args: Namespace) -> None:
        keep = args.keep
        if keep < 0:
            self.println(
                "<Please specify a positive number for how many messages to keep>"
            )
            return
        self.conversation.history = self.conversation.history[-keep:]
        self.println(f"<Cropped conversation to the last {keep} messages>")

    def who(self, _: Namespace) -> None:
        self.println("<Available Personas:>")
        for persona in self.available_personas:
            self.println(f"  {persona}")

    def to(self, args: Namespace) -> None:
        persona_name = args.name
        if persona_name not in self.beh.env.list_personas():
            self.println("<'{persona_name}' is not a valid persona>")
            return
        self.beh.set_persona(persona_name)

    def println(self, text: str, flush: bool = False):
        print(text, file=self.user_io.text_out, flush=flush)

    def readln(self) -> str:
        return self.user_io.text_in.readline()

    def _save_last_conversation(self):
        self.last_conv_path.write_text(
            self.conversation.model_dump_json(), encoding="utf-8"
        )

    def _save_conversation(self, name: str):
        path = self.conversation_base_path / (name + ".json")
        self.conversation.name = name
        path.write_text(self.conversation.model_dump_json(), encoding="utf-8")
        self._save_last_conversation()


def _build_parser(repl: Repl, parser: ArgumentParser):
    subparsers = parser.add_subparsers()
    quit_parser = subparsers.add_parser("quit", help="Quit", aliases=["q"])
    quit_parser.set_defaults(callback=repl.quit)

    save_parser = subparsers.add_parser("save", help="Save the conversation")
    save_parser.set_defaults(callback=repl.save)
    save_parser.add_argument(
        "name", nargs="?", type=str, help="The name of the conversation"
    )

    load_parser = subparsers.add_parser("load", help="Load the conversation")
    load_parser.set_defaults(callback=repl.load)
    load_parser.add_argument(
        "name", nargs=1, type=str, help="Name of the conversation to load"
    )

    new_parser = subparsers.add_parser("new", help="Create a new conversation")
    new_parser.set_defaults(callback=repl.new)

    help_parser = subparsers.add_parser("help", help="Show help", aliases=["h", "?"])
    help_parser.set_defaults(callback=repl.help)

    forget_parser = subparsers.add_parser("forget", help="Quit without saving")
    forget_parser.set_defaults(callback=repl.forget)

    remember_parser = subparsers.add_parser("remember", help="Save and quit")
    remember_parser.set_defaults(callback=repl.remember)

    export_parser = subparsers.add_parser(
        "export", help="Export the conversation as a markdown file"
    )
    export_parser.set_defaults(callback=repl.export)

    len_parser = subparsers.add_parser(
        "length", help="Print the length of the conversation", aliases=["len"]
    )
    len_parser.set_defaults(callback=repl.len)

    last_parser = subparsers.add_parser("last", help="Print the last n messages")
    last_parser.set_defaults(callback=repl.last)

    crop_parser = subparsers.add_parser(
        "crop", help="Crop the conversation to the last n messages"
    )
    crop_parser.set_defaults(callback=repl.crop)
    crop_parser.add_argument(
        "keep", nargs=1, type=int, help="How many messages to keep"
    )

    who_parser = subparsers.add_parser(
        "who", help="Print the names of available personas"
    )
    who_parser.set_defaults(callback=repl.who)

    to_parser = subparsers.add_parser(
        "talk-to",
        help="Set which persona will answer your requests",
        aliases=["ask", "to", "talk-with", "talk"],
    )
    to_parser.set_defaults(callback=repl.to)


def _handle_cmd(parser: ArgumentParser, cmd: str):
    args = parser.parse_args(shlex.split(cmd))
    args.callback(args)
