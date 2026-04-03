from typing import Callable

from bond.behaviours.behaviour_signal import BehaviourSignal
from bond.behaviours.single_turn import SingleTurn
from bond.bond_environment import BondEnvironment
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.io.aoe import AgentOutputEnvironment
from bond.persona import Persona
from bond.providers.provider import build_toolbox
from bond.tools.tool import ToolEnvironment


class LoopBehaviour:
    persona: Persona
    persona_id: str
    turn: SingleTurn
    running: bool

    def __init__(
        self,
        conversation: Conversation,
        environment: BondEnvironment,
        aoe: AgentOutputEnvironment,
        signal_receiver: Callable[[], BehaviourSignal],
        notifier: Callable[[str], None],
        command_handler: Callable[[str], None] | None,
        tool_environment: ToolEnvironment,
        persona_id: str,
        stream: bool = False,
        allow_shell_executions: bool = False,
        user_name: str | None = None,
        allowed_personas: list[str] | None = None,
        **additional_chat_completion_arguments,
    ):
        self.conversation = conversation
        self.env = environment
        self.aoe = aoe
        self.signal_receiver = signal_receiver
        self.notifier = notifier
        self.command_handler = command_handler
        self.tool_environment = tool_environment
        self.persona_id = persona_id
        self.stream = stream
        self.allow_shell_executions = allow_shell_executions
        self.user_name = user_name
        self.allowed_personas = allowed_personas
        self.additional_chat_completion_arguments = additional_chat_completion_arguments

        self.running = False
        self.set_persona(persona_id, False)
        self.set_conversation(conversation)

    def set_persona(self, persona_id: str, update_conversation: bool):
        self.persona = self.env.get_persona(persona_id)
        self.persona_id = persona_id
        if update_conversation:
            self.conversation.current_persona = persona_id
        self._build_turn()

    def set_conversation(self, conversation: Conversation):
        self.conversation = conversation
        if self.conversation.current_persona is not None:
            if (
                self.allowed_personas is None
                or conversation.current_persona in self.allowed_personas
            ):
                self.set_persona(self.conversation.current_persona, False)
            else:
                self.notifier(
                    f"The persona {self.conversation.current_persona} of this conversation is not available in chats."
                )

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
            endpoint=provider.chat_completions(),
            model=self.persona.model,
            aoe=self.aoe,
            system_message=self.persona.system_prompt,
            toolbox=toolbox,
            tool_environment=self.tool_environment,
            model_display_name=self.persona.name,
            stream=self.stream,
            allow_shell_executions=self.allow_shell_executions,
            **self.additional_chat_completion_arguments,
        )

    def run(self):
        if self.running:
            raise RuntimeError("Already running")
        self.running = True
        while self.running:
            signal = self.signal_receiver()
            if signal.type == "command":
                if self.command_handler is not None:
                    try:
                        self.command_handler(signal.command)
                    except Exception as e:
                        self.notifier(f"{e}")
                else:
                    self.notifier("No command handler")
            elif signal.type == "stop":
                self.running = False
            elif signal.type == "prompt":
                self.conversation.current_persona = self.persona_id
                self.conversation.add_message(
                    ConversationMessage.create_user_message(
                        signal.prompt, user_name=self.user_name or "User"
                    )
                )
                try:
                    self.turn.run(self.conversation)
                except Exception as e:
                    self.notifier(f"{e}")
            else:
                raise NotImplementedError()
