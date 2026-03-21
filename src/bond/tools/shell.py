import subprocess
from contextlib import contextmanager
from threading import local

from bond.tools import tool

_shell_command_locals = local()


@contextmanager
def allow_shell_commands():
    global _shell_command_locals
    if not hasattr(_shell_command_locals, "allow_shell_commands"):
        _shell_command_locals.allow_shell_commands = False
    if _shell_command_locals.allow_shell_commands:
        raise RuntimeError("Cannot nest shell context managers")
    _shell_command_locals.allow_shell_commands = True
    try:
        yield
    finally:
        _shell_command_locals.allow_shell_commands = False


def run_shell_commands(commands: str, explaination: str):
    """
    Run a list of shell commands.
    The user has to allow these commands manually.
    Make your commands simple and expressive so that the user can easily understand them.
    Provide an explaination to help the user understand what you are doing.

    Args:
        commands (str): The commands to execute
        explaination (str): The explaination of the commands

    Returns:
        str: The last 10 lines of the output
    """
    global _shell_command_locals
    if (
        not hasattr(_shell_command_locals, "allow_shell_commands")
        or not _shell_command_locals.allow_shell_commands
    ):
        raise RuntimeError(
            "Shell commands are disabled. Wrap the call with 'with allow_shell_commands():'"
        )
    env = tool.get_tool_environment()
    if not env.is_interactive():
        return "error: the tool is not running in interactive mode, so the user cannot grant you access to the shell tool right now."
    prompt = (
        "\n\n\nBond wants to run the following commands:\n  "
        + "\n  ".join(commands.splitlines())
        + "\nBond: "
        + explaination
        + "\nDo you want to run these commands?"
    )
    if not env.ask_confirmation(prompt):
        return "error: the user cannot accept your requests right now."

    result = subprocess.run(commands, text=True, shell=True, capture_output=True)
    lines = result.stdout.splitlines()[-10:]
    err_lines = result.stderr.splitlines()[-10:]
    output = ["stdout:"] + lines
    if len(err_lines) > 0:
        output.append("stderr:")
        output += err_lines
    return "\n".join(output)
