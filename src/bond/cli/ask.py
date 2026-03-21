import sys
from argparse import ArgumentParser
from pathlib import Path

from bond.behaviours.single_turn import SingleTurn
from bond.bond_environment import DynamicBondEnvironment
from bond.config import BondConfig
from bond.io.io_env import IOEnvironment
from bond.tools import global_toolbox, tool


def main():

    # Parse args
    parser = ArgumentParser("Ask Bond")
    parser.add_argument("first", type=str)
    parser.add_argument("second", type=str, nargs="?")
    parser.add_argument("--show-thoughts", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")

    args = parser.parse_args()
    request = args.first if args.second is None else args.second

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
        )
    )
    io_environment = IOEnvironment(
        text_in=sys.stdin,
        text_out=sys.stdout,
        thought_out=sys.stdout if args.show_thoughts else None,
    )

    # Get persona
    persona: str = (
        config.ask.get_default_persona() if args.second is None else args.first
    )
    if persona not in config.ask.personas:
        raise ValueError(
            f"not a valid persona: {persona}. Available personas: {'\n'.join(config.ask.personas)}"
        )
    allow_shell = "shell" in env.get_persona(persona).toolbox

    turn = SingleTurn(
        env,
        persona,
        tool_environment=tool_environment,
        io_environment=io_environment,
        allow_shell_executions=allow_shell,
    )
    conversation = turn.run(request)
    # TODO: save conversation as last-ask so the user can followup


if __name__ == "__main__":
    main()
