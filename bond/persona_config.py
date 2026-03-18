from typing import List, Literal

from pydantic import BaseModel, Field

BehaviorType = Literal["simple", "agent_loop"]
AvailableTools = Literal["web_search", "code_interpreter", "file_io"]


class PersonaConfig(BaseModel):
    """Configuration for an AI persona."""

    name: str = Field(..., description="Name of the persona")
    model: str = Field(..., description="Mistral model to use (e.g., 'mistral-small')")
    system_prompt: str = Field(
        ..., description="System prompt to set the assistant's role"
    )
    behavior: BehaviorType = Field(
        "simple", description="Response behavior: simple or agent loop"
    )
    tools: List[AvailableTools] = Field(
        default_factory=list, description="List of tools available to the persona"
    )
    temperature: float = Field(
        0.7, description="Temperature for response randomness (0.0-1.0)"
    )
    max_tokens: int = Field(2048, description="Maximum tokens in response")
    max_context: int = Field(8192, description="Maximum size of the context")


def get_chatter() -> PersonaConfig:
    return PersonaConfig(
        name="Chatter",
        model="mistral-small",
        system_prompt="You are a chat bot with the task to assist the user to the best of your abilities. Think before you give your answer and make sure your answer is correct.",
        behavior="simple",
        tools=[],
        temperature=0.4,
        max_tokens=2048,
        max_context=8192,
    )


def get_code_assistant() -> PersonaConfig:
    return PersonaConfig(
        name="code_assistant",
        model="mistral-small",
        system_prompt="You are a helpful coding assistant. Always provide code examples.",
        behavior="agent_loop",
        tools=["code_interpreter", "web_search"],
        temperature=0.3,
        max_tokens=2048,
        max_context=8192,
    )


if __name__ == "__main__":
    code_assistant = get_code_assistant()
    print(code_assistant.model_dump_json(indent=2))
