from argparse import ArgumentParser
from pathlib import Path

from bond.behaviours.single_turn import SingleTurn
from bond.bond_environment import DynamicBondEnvironment
from bond.config import BondConfig
from bond.tools import global_toolbox, tool


def main():
    parser = ArgumentParser("Ask Bond")
    parser.add_argument("first", type=str)
    parser.add_argument("second", type=str, nargs="?")

    args = parser.parse_args()

    env_path = Path("~/.config/bond").expanduser().absolute()
    config_path = env_path / "config.json"

    config = BondConfig.load_from(config_path)
    env = DynamicBondEnvironment(
        env_path,
        {
            k: v
            for k, v in global_toolbox.build_global_toolsets().items()
            if k in config.ask.tools
        },
    )

    persona: str = (
        config.ask.get_default_persona() if args.second is None else args.first
    )
    if persona not in config.ask.personas:
        raise ValueError(
            f"not a valid persona: {persona}. Available personas: {'\n'.join(config.ask.personas)}"
        )
    request = args.first if args.second is None else args.second

    tool.set_interactive(True)
    allow_shell = "shell" in env.get_persona(persona).toolbox

    turn = SingleTurn(env, persona, allow_shell_executions=allow_shell)
    result, conversation = turn.run(request)
    print(result)


if __name__ == "__main__":
    main()
