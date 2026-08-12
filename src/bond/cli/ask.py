import os
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from bond.behaviours.single_turn import SingleTurn
from bond.config import BondConfig, get_default_persona
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.environment.std_event_handler import StdEventHandler
from bond.environment.std_signal_receiver import StdSignalReceiver
from bond.runtime import BondRuntime
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import Toolbox

from . import logger


def _get_input_file_content(args: Namespace):
    if args.input_file:
        if_path = Path(args.input_file).expanduser().absolute()
        if not if_path.is_file():
            raise ValueError(f"Not a file: {args.input_file}")
        return if_path.read_text()
    if not os.isatty(sys.stdin.fileno()):
        return sys.stdin.read()
    return None


def main():
    user_name = "User"

    # Parse args
    parser = ArgumentParser("Ask Bond")
    parser.add_argument("first", type=str)
    parser.add_argument("second", type=str, nargs="?")
    parser.add_argument("--show-thoughts", action="store_true")
    parser.add_argument("--show-tool-output", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--input-file", "-i", type=str)
    parser.add_argument("--output-file", "-o", type=str)
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--no-save", action="store_true")

    args = parser.parse_args()
    request: str = args.first if args.second is None else args.second
    show_thoughts: bool = args.show_thoughts
    show_tool_output: bool = args.show_tool_output
    stream: bool = not args.no_stream if not show_thoughts else False
    no_save: bool = args.no_save
    if (input_file_content := _get_input_file_content(args)) is not None:
        request = input_file_content + "\n\n\n" + request
    is_interactive = not args.non_interactive
    cwd = Path(os.getcwd())

    # Setup environment
    env_path = Path("~/.config/bond").expanduser().absolute()
    conv_path = Path("~/.local/share/bond").expanduser().absolute()
    config_path = env_path / "config.json"
    config = BondConfig.load_from(config_path)

    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic(env_path)

    persona_id: str = (
        get_default_persona(config.ask) if args.second is None else args.first
    )
    if persona_id not in config.ask.personas:
        raise ValueError(
            f"not a valid persona: {persona_id}. Available personas: {'\n'.join(config.ask.personas)}"
        )
    persona = runtime.get_persona(persona_id)
    provider = runtime.get_provider(persona.provider)
    toolbox = Toolbox(runtime.get_tools(persona.toolbox))

    # Setup conversation
    conversation = Conversation()
    conversation.add_message(
        ConversationMessage.create_user_message(request, user_name)
    )

    tool_call_context = ToolCallContext(
        persona=persona_id,
        stdout=sys.stdout,
        stdin=sys.stdin,
        is_interactive=is_interactive,
        cwd=cwd,
        logger=logger,
    )
    signal_receiver = StdSignalReceiver()
    event_handler = StdEventHandler(signal_receiver, show_thoughts, show_tool_output)

    # Setup turn
    allow_shell = "shell" in persona.toolbox
    turn = SingleTurn(
        provider=provider,
        model=persona.model,
        event_handler=event_handler,
        signal_receiver=signal_receiver,
        tool_call_context=tool_call_context,
        system_message=persona.system_prompt,
        toolbox=toolbox,
        model_display_name=persona.name,
        stream=stream,
        allow_shell_executions=allow_shell,
    )
    signal_receiver.link(lambda: persona.name)

    # Run turn

    turn.run(conversation)

    if not no_save:
        save_path = conv_path / "last-ask.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(conversation.model_dump_json(), encoding="utf-8")


if __name__ == "__main__":
    main()
