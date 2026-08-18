import sys
from argparse import ArgumentParser
from pathlib import Path

from bond.runtime import BondRuntime


def list_plugins():
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic(
        Path("~/.config/bond").expanduser().absolute(), enable_plugins=False
    )
    plugins = runtime.list_plugins()
    if len(plugins) == 0:
        print("No plugins found")
        return
    print("Plugins:\n  " + "\n  ".join(plugins))


def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    plugins_parser = subparsers.add_parser("plugins")
    plugins_parser.set_defaults(callback=list_plugins)

    args = parser.parse_args()
    if not hasattr(args, "callback"):
        print("Missing command")
        return 1
    args.callback()
    return 0


if __name__ == "__main__":
    sys.exit(main())
