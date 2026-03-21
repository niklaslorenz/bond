import subprocess
from shlex import shlex

from bond.tools import tool

from . import logger


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
    print(
        "\n\n\nBond wants to run the following commands:\n  "
        + "\n  ".join(commands.splitlines())
    )
    print("Bond: " + explaination)
    print("Do you want to run these commands?")
    if tool.is_interactive():
        while True:
            grant = input("[yes|no] > ").lower()
            if grant == "no" or grant == "n":
                return "error: the user has rejected your request."
            if grant == "yes" or grant == "y":
                break
    else:
        return "error: the user cannot accept your requests right now."

    result = subprocess.run(commands, text=True, shell=True, capture_output=True)
    lines = result.stdout.splitlines()[-10:]
    err_lines = result.stderr.splitlines()[-10:]
    output = ["stdout:"] + lines
    if len(err_lines) > 0:
        output.append("stderr:")
        output += err_lines
    return "\n".join(output)
