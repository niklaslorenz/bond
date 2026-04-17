from typing import Callable

from bond.behaviours.behaviour_event import (ChangePersonaEvent,
                                             CommandResponseEvent, ErrorEvent,
                                             NotifyEvent,
                                             RestoreConversationEvent,
                                             StopEvent, WaitingForInputEvent)
from bond.behaviours.behaviour_signal import (CommandSignal, PromptSignal,
                                              StopSignal)
from bond.behaviours.single_turn import SingleTurn
from bond.behaviours.types import (IBehaviourEventHandler,
                                   IBehaviourSignalReceiver)
from bond.bond_environment import BondEnvironment
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.persona import Persona
from bond.providers.provider import build_toolbox
from bond.tools.tool import ToolEnvironment

from . import logger


class LoopBehaviour:
    persona: Persona
    persona_id: str
    turn: SingleTurn
    running: bool

    def __init__(
        self,
        conversation: Conversation,
        environment: BondEnvironment,
        event_handler: IBehaviourEventHandler,
        signal_receiver: IBehaviourSignalReceiver,
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
        self.event_handler = event_handler
        self.signal_receiver = signal_receiver
        self.command_handler = command_handler
        self.tool_environment = tool_environment
        self.persona_id = persona_id
        self.new_conversation_persona = persona_id
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
        self.event_handler(
            ChangePersonaEvent(name=self.persona.name, provider=self.persona.provider)
        )

    def set_conversation(self, conversation: Conversation):
        self.conversation = conversation
        if self.conversation.current_persona is not None:
            if (
                self.allowed_personas is None
                or conversation.current_persona in self.allowed_personas
            ):
                self.set_persona(self.conversation.current_persona, False)
            else:
                self.event_handler(
                    NotifyEvent(
                        message=f"The persona {self.conversation.current_persona} of this conversation is not available in chats."
                    )
                )
        self.event_handler(RestoreConversationEvent(conversation=conversation))

    def new_conversation(self):
        self.set_conversation(
            Conversation(current_persona=self.new_conversation_persona)
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
            event_handler=self.event_handler,
            signal_receiver=self.signal_receiver,
            tool_environment=self.tool_environment,
            system_message=self.persona.system_prompt,
            toolbox=toolbox,
            model_display_name=self.persona.name,
            stream=self.stream,
            allow_shell_executions=self.allow_shell_executions,
            **self.additional_chat_completion_arguments,
        )

    def run(self):
        logger.info("Starting Loop Behaviour")
        if self.running:
            raise RuntimeError("Already running")
        self.running = True
        while self.running:
            self.event_handler(WaitingForInputEvent())
            signal = self.signal_receiver.get()
            if isinstance(signal, CommandSignal):
                if self.command_handler is not None:
                    try:
                        self.command_handler(signal.command)
                        self.event_handler(CommandResponseEvent())
                    except Exception as e:
                        self.event_handler(
                            NotifyEvent(
                                message=f"Error in event handler: {type(e)}, {e}"
                            )
                        )
                else:
                    self.event_handler(NotifyEvent(message="Error: No command handler"))
            elif isinstance(signal, StopSignal):
                self.running = False
            elif isinstance(signal, PromptSignal):
                self.conversation.current_persona = self.persona_id
                self.conversation.add_message(
                    ConversationMessage.create_user_message(
                        signal.prompt, user_name=self.user_name or "User"
                    )
                )
                try:
                    self.turn.run(self.conversation)
                except Exception as e:
                    self.event_handler(ErrorEvent(error=e, critical=False))
            else:
                self.event_handler(
                    ErrorEvent(
                        error=ValueError(
                            f"Invalid behaviour signal type: {type(signal)}"
                        ),
                        critical=False,
                    )
                )
        self.event_handler(StopEvent())
        logger.info("Stopping Loop Behaviour")
