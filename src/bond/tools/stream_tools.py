from bond.tools import tool


def write_to_output(text: str) -> str:
    """
    Write data to the designated output stream.

    Args:
        text (str): The text to write to the output

    Returns:
        An error or success message
    """
    env = tool.get_tool_environment()
    if env.supports_stdout():
        env.handle_stdout(text, True)
        return "success: data written to output"
    else:
        return "error: no output stream"
