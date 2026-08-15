from bond.tools import tool


@tool.tool(
    name="write_to_output",
    description="""
    Write data to the designated output stream.
    """,
    parameters={
        "text": tool.FunctionParameter(
            type="string", description="The text to write to the output"
        )
    },
    required=["text"],
)
def write_to_output(text: str) -> str:
    env = tool.get_tool_environment()
    if env.supports_stdout():
        assert (stdout := env.stdout()) is not None
        stdout.write(text)
        return "success: data written to output"
    else:
        return "error: no output stream"
