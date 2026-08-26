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
def write_to_output(context: tool.ToolCallContext, text: str) -> str:
    if context.stdout is not None:
        context.stdout.write(text)
        return "success: data written to output"
    else:
        return "error: no output stream"
