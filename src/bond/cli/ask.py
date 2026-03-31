import os
from argparse import ArgumentParser
from pathlib import Path

from bond.behaviours.single_turn import SingleTurn
from bond.bond_environment import DynamicBondEnvironment
from bond.config import BondConfig, get_default_persona
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.io.stdio import StdAoe, StdIoToolEnvironment
from bond.providers.provider import build_toolbox
from bond.tools import global_toolbox, tool


def main():
    user_name = "User"

    # Parse args
    parser = ArgumentParser("Ask Bond")
    parser.add_argument("first", type=str)
    parser.add_argument("second", type=str, nargs="?")
    parser.add_argument("--show-thoughts", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--input-file", "-i", type=str)
    parser.add_argument("--output-file", "-o", type=str)
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--no-save", action="store_true")

    args = parser.parse_args()
    request: str = args.first if args.second is None else args.second
    show_thoughts: bool = args.show_thoughts
    stream: bool = not args.no_stream if not show_thoughts else False
    no_save: bool = args.no_save

    # Setup environment
    env_path = Path("~/.config/bond").expanduser().absolute()
    conv_path = Path("~/.local/share/bond").expanduser().absolute()
    config_path = env_path / "config.json"
    config = BondConfig.load_from(config_path)

    env = DynamicBondEnvironment(
        env_path, global_toolbox.get_toolsets(config.ask.tools)
    )
    tool_environment = StdIoToolEnvironment(
        work_dir=lambda: Path(os.getcwd()), is_interactive=True
    )
    aoe = StdAoe()

    # Get environment entities
    persona_name: str = (
        get_default_persona(config.ask) if args.second is None else args.first
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
    conversation.add_message(
        ConversationMessage.create_user_message(request, user_name)
    )

    # Run turn
    allow_shell = "shell" in persona.toolbox
    turn = SingleTurn(
        endpoint=provider.chat_completions(),
        model=persona.model,
        aoe=aoe,
        tool_environment=tool_environment,
        system_message=persona.system_prompt,
        toolbox=toolbox,
        model_display_name=persona.name,
        stream=stream,
        allow_shell_executions=allow_shell,
    )
    turn.run(conversation)

    if not no_save:
        save_path = conv_path / "last-ask.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(conversation.model_dump_json(), encoding="utf-8")


if __name__ == "__main__":
    main()
