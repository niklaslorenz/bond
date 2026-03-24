import sys
from argparse import ArgumentParser
from pathlib import Path

from bond.behaviours.single_turn import SingleTurn
from bond.bond_environment import DynamicBondEnvironment
from bond.config import BondConfig
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.io.io_env import IOEnvironment
from bond.io.stream import WritethroughWrapper
from bond.providers.provider import build_toolbox
from bond.tools import global_toolbox, tool


def main():
    user_name = "user"

    # Parse args
    parser = ArgumentParser("Ask Bond")
    parser.add_argument("first", type=str)
    parser.add_argument("second", type=str, nargs="?")
    parser.add_argument("--show-thoughts", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--input-file", "-i", type=str)
    parser.add_argument("--output-file", "-o", type=str)
    parser.add_argument("--no-stream", action="store_true")

    args = parser.parse_args()
    request: str = args.first if args.second is None else args.second
    stream: bool = not args.no_stream

    # Setup environment
    env_path = Path("~/.config/bond").expanduser().absolute()
    config_path = env_path / "config.json"
    config = BondConfig.load_from(config_path)
    env = DynamicBondEnvironment(
        env_path, global_toolbox.get_toolsets(config.ask.tools)
    )
    tool_environment = tool.ToolEnvironment(
        interaction_io=(
            tool.BidirectionalTextIO(text_in=sys.stdin, text_out=sys.stdout)
            if not args.non_interactive
            else None
        ),
        tool_in=(
            open(args.input_file, "r")
            if args.input_file is not None
            else sys.stdin if not sys.stdin.isatty() else None
        ),
        tool_out=(
            open(args.output_file, "w") if args.output_file is not None else sys.stdout
        ),
    )
    io_environment = IOEnvironment(
        text_in=sys.stdin,
        text_out=WritethroughWrapper(sys.stdout),
        thought_out=sys.stdout if args.show_thoughts else None,
    )

    # Get environment entities
    persona_name: str = (
        config.ask.get_default_persona() if args.second is None else args.first
    )
    if persona_name not in config.ask.personas:
        raise ValueError(
            f"not a valid persona: {persona_name}. Available personas: {'\n'.join(config.ask.personas)}"
        )
    persona = env.get_persona(persona_name)
    provider = env.get_provider(persona.provider)
    toolbox: tool.Toolbox = build_toolbox(
        provider,
        [tool for toolset in persona.toolbox for tool in env.get_toolset(toolset)],
    )

    # Setup conversation
    conversation = Conversation()
    if persona.system_prompt is not None:
        conversation.add_message(
            ConversationMessage.create_system_message(persona.system_prompt)
        )
    conversation.add_message(
        ConversationMessage.create_user_message(request, user_name)
    )

    # Run turn
    allow_shell = "shell" in persona.toolbox
    turn = SingleTurn(
        provider,
        persona.model,
        toolbox,
        io_environment=io_environment,
        tool_environment=tool_environment,
        model_display_name=persona_name,
        stream=stream,
        allow_shell_executions=allow_shell,
    )
    turn.run(conversation)
    # TODO: save conversation as last-ask so the user can followup


if __name__ == "__main__":
    main()
