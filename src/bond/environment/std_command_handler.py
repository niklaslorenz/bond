import sys
from argparse import Namespace, _SubParsersAction
from pathlib import Path

from bond.behaviours.types import IBehaviourEventHandler
from bond.conversation.types import (AssistantMessage, SystemMessage,
                                     TextChunk, UserMessage,
                                     parse_chunks_content)
from bond.environment.base_command_handler import BaseCommandHandler
from bond.environment.types import IBehaviourSignalHandler


class StdCommandHandler(BaseCommandHandler):

    def __init__(
        self,
        event_handler: IBehaviourEventHandler,
        signal_handler: IBehaviourSignalHandler,
        conversation_base_path: Path,
        last_conv_path: Path,
        available_personas: list[str],
        save_on_quit: bool,
        show_thoughts: bool,
    ):
        super().__init__(
            event_handler,
            signal_handler,
            conversation_base_path=conversation_base_path,
            last_conv_path=last_conv_path,
            available_personas=available_personas,
            save_on_quit=save_on_quit,
        )
        self._show_thoughts = show_thoughts

    # Modified commands

    def clear_tool_calls(self, args: Namespace) -> None:
        super().clear_tool_calls(args)
        self.notify("Cleared tool calls")

    def load(self, args: Namespace) -> None:
        super().load(args)
        if args.name is None:
            return
        self.notify(
            f"loaded '{args.name}' with {len(self.beh.conversation.history)} messages"
        )

    def new(self, args: Namespace) -> None:
        super().new(args)
        self.notify("New Conversation")

    def crop(self, args: Namespace) -> None:
        self.notify(f"Cropped conversation to the last {args.keep} messages")

    def delete(self, args: Namespace) -> None:
        self.notify(f"Removed {args.n} messages")

    # New commands

    def help(self, _: Namespace) -> None:
        self.notify(self.parser.format_help())

    def len(self, _: Namespace) -> None:
        self.notify(f"{len(self.beh.conversation.history)} messages")

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
                print(f"{message.author}:")

                text, think = parse_chunks_content(msg.content)
                if think is not None and self._show_thoughts:
                    print(f"[THINK]\n{think}\n[/THINK]")
                if text is not None:
                    print(f"{text}\n")

                for chunk in msg.content:
                    if isinstance(chunk, TextChunk):
                        print(chunk.text, end="")
                print("\n")

    def who(self, _: Namespace) -> None:
        self.notify(
            "Available Personas:\n"
            + "\n".join([f"  {persona}" for persona in self.available_personas])
        )

    # overridden behavioural methods

    def handle_shell_command(
        self, cmd: str, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr
    ):
        super().handle_shell_command(cmd, stdin, stdout, stderr)

    def build_parser(self, subparsers: _SubParsersAction):
        super().build_parser(subparsers)

        help_parser = subparsers.add_parser(
            "help", help="Show help", aliases=["h", "?"], exit_on_error=False
        )
        help_parser.set_defaults(callback=self.help)

        len_parser = subparsers.add_parser(
            "length",
            help="Print the length of the conversation",
            aliases=["len"],
            exit_on_error=False,
        )
        len_parser.set_defaults(callback=self.len)

        last_parser = subparsers.add_parser(
            "last", help="Print the last n messages", exit_on_error=False
        )
        last_parser.set_defaults(callback=self.last)
        last_parser.add_argument(
            "n", nargs="?", type=int, default=1, help="Number of messages to print"
        )

        who_parser = subparsers.add_parser(
            "who", help="Print the names of available personas", exit_on_error=False
        )
        who_parser.set_defaults(callback=self.who)
