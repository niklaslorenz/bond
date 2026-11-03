import asyncio
from argparse import ArgumentParser
from pathlib import Path

from bond import util

from ._interactive import run_interactive_session


def build_parser():
    parser = ArgumentParser("Chat with Bond")
    parser.add_argument("--conversation-path", type=str)
    parser.add_argument("--environment-path", type=str)
    parser.add_argument("--no-save-after-turn", action="store_true")
    parser.add_argument("--show-thoughts", action="store_true")
    parser.add_argument("--show-tool-output", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--debug", action="store_true")

    return parser


def main():
    args = build_parser().parse_args()
    util.setup_logger(args.debug, "chat.log")

    show_thoughts: bool = args.show_thoughts
    stream: bool = not args.no_stream if not show_thoughts else False

    conv_path = (
        Path(args.conversation_path or "~/.local/share/bond").expanduser().absolute()
    )
    env_path = Path(args.environment_path or "~/.config/bond/").expanduser().absolute()

    asyncio.run(
        run_interactive_session(
            conv_path=conv_path,
            env_path=env_path,
            conv_name="last-conv",
            config_section="chat",
            show_thoughts=show_thoughts,
            show_tool_output=args.show_tool_output,
            stream=stream,
            is_interactive=not args.non_interactive,
            save_after_turn=not args.no_save_after_turn,
        )
    )


if __name__ == "__main__":
    main()
