import sys
from typing import Any, Callable

from bond.behaviours.single_turn import SingleTurn
from bond.bond_environment import BondEnvironment
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.io.agent_output_environment import AgentOutputEnvironment
from bond.persona import Persona
from bond.providers.provider import build_toolbox
from bond.tools.tool import BidirectionalTextIO, ToolEnvironment

CommandHandler = Callable[[str], None]


class LoopBehaviour:
    env: BondEnvironment
    aoe: AgentOutputEnvironment
    user_io: BidirectionalTextIO
    persona_name: str
    stream: bool
    allow_shell_executions: bool
    additional_chat_completion_arguments: dict[str, Any]
    running: bool

    persona: Persona
    turn: SingleTurn

    def __init__(
        self,
        environment: BondEnvironment,
        aoe: AgentOutputEnvironment,
        user_io: BidirectionalTextIO,
        tool_environment: ToolEnvironment,
        persona_name: str,
        stream: bool = False,
        allow_shell_executions: bool = False,
        command_handler: CommandHandler | None = None,
        user_name: str | None = None,
        **additional_chat_completion_arguments,
    ):
        self.env = environment
        self.aoe = aoe
        self.user_io = user_io
        self.tool_environment = tool_environment
        self.persona_name = persona_name
        self.stream = stream
        self.allow_shell_executions = allow_shell_executions
        self.command_handler = command_handler
        self.user_name = user_name
        self.additional_chat_completion_arguments = additional_chat_completion_arguments
        self.running = False
        self.set_persona(persona_name)

    def set_persona(self, persona_name: str):
        self.persona = self.env.get_persona(persona_name)
        self._build_turn()

    def _build_turn(self):
        provider = self.env.get_provider(self.persona.provider)
        toolbox = build_toolbox(
            provider,
            [
                tool
                for toolset in self.persona.toolbox
                for tool in self.env.get_toolset(toolset)
            ],
        )
        self.turn = SingleTurn(
            provider=provider,
            model=self.persona.model,
            toolbox=toolbox,
            aoe=self.aoe,
            tool_environment=self.tool_environment,
            model_display_name=self.persona.name,
            stream=self.stream,
            allow_shell_executions=self.allow_shell_executions,
            **self.additional_chat_completion_arguments,
        )
        pass

    def run(self, conversation: Conversation):
        if self.running:
            raise RuntimeError("Already running")
        self.running = True
        while self.running:
            self.user_io.text_out.write(f"[to {self.persona.name}]> ")
            user_msg = self.user_io.text_in.readline()
            stripped_msg = user_msg.strip()

            if len(stripped_msg) == 0:
                continue
            if self.command_handler is not None and stripped_msg[0] == ":":
                try:
                    self.command_handler(stripped_msg[1:])
                except Exception as e:
                    print(file=sys.stderr)
                continue

            conversation.add_message(
                ConversationMessage.create_user_message(
                    user_msg, user_name=self.user_name or "User"
                )
            )
            try:
                self.turn.run(conversation)
            except Exception as e:
                print(f"{e}", file=self.user_io.text_out)
