import asyncio
from argparse import ArgumentParser
from pathlib import Path

from bond import util

from ._interactive import run_interactive_session


def build_parser():
    parser = ArgumentParser("Follow up on the last ask")
    parser.add_argument("--show-thoughts", action="store_true")
    parser.add_argument("--show-tool-output", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--debug", action="store_true")

    return parser


def main():
    args = build_parser().parse_args()
    util.setup_logger(args.debug, "followup.log")

    show_thoughts: bool = args.show_thoughts
    stream: bool = not args.no_stream if not show_thoughts else False

    conv_path = Path("~/.local/share/bond").expanduser().absolute()
    env_path = Path("~/.config/bond/").expanduser().absolute()

    asyncio.run(
        run_interactive_session(
            conv_path=conv_path,
            env_path=env_path,
            # Continue the conversation that `ask` saved
            conv_name="last-ask",
            config_section="chat",
            show_thoughts=show_thoughts,
            show_tool_output=args.show_tool_output,
            stream=stream,
            is_interactive=not args.non_interactive,
            save_after_turn=True,
        )
    )


if __name__ == "__main__":
    main()
