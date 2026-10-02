from bond.tools import tool


@tool.tool(
    name="test_confirmation",
    description="""
    A testing tool for the user confirmation interface.
    You can specify a text that will be displayed to the user
    and the user can choose to accept or decline your request.
    Because this is a test tool, the user's action does not
    really do anything. You will just receive the information
    whether the user has accepted or not. 
    """,
    parameters={
        "request": tool.FunctionParameter(
            type="string", description="Your request that will be shown to the user"
        ),
    },
    required=["request"],
)
def test_confirmation(context: tool.ToolCallContext, request: str):
    if context.ask_confirmation(request):
        return "The user has accepted your request"
    else:
        return "The user has denied your request"
