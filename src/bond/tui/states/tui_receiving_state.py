from dataclasses import dataclass

from bond.behaviours import behaviour_event
from bond.conversation.types import parse_chunks_content
from bond.tui.states.tui_state import TuiState
from bond.tui.types import ITuiState, ITuiStateMachine
from bond.tui.widgets import ChatMessage


@dataclass
class TuiReceivingState(TuiState):
    msg: ChatMessage

    def __init__(self, machine: ITuiStateMachine, msg: ChatMessage):
        super().__init__(machine)
        self.msg = msg

    def on_enter(self, source: ITuiState):
        self.machine.get_app().set_status("Receiving")

    def handle_response_end_behaviour_event(
        self, event: behaviour_event.ResponseEndEvent
    ):
        from . import TuiWaitingState

        self.machine.change_state(TuiWaitingState(self.machine))

    def handle_append_message_chunk_behaviour_event(
        self, event: behaviour_event.AppendMessageChunkEvent
    ):
        if (
            len(event.chunk.choices) == 0
            or event.chunk.choices[0].delta.content is None
        ):
            return
        text, think = parse_chunks_content(event.chunk.choices[0].delta.content)
        if think is not None:
            self.msg.append_thinking(think)
        if text is not None:
            self.msg.append_text(text)
