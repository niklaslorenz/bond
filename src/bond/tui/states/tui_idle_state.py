from dataclasses import dataclass

from bond.behaviours import behaviour_event
from bond.behaviours.behaviour_signal import CommandSignal, PromptSignal
from bond.tui.event import UserInputEvent
from bond.tui.states.tui_state import TuiState
from bond.tui.states.tui_stop_state import TuiStopState
from bond.tui.types import ITuiState


@dataclass
class TuiIdleState(TuiState):
    def on_enter(self, source: ITuiState):
        self.machine.get_app().set_status("Idle")

    def handle_user_input_event(self, event: UserInputEvent):
        self.machine.get_app().clear_input()
        self.machine.get_app().scroll_to_end()
        if event.input_type == "command":
            self.machine.send_signal(CommandSignal(command=event.message))
            from . import TuiWaitForCommandResponseState

            self.machine.change_state(TuiWaitForCommandResponseState(self.machine))
        elif event.input_type == "prompt":
            self.machine.send_signal(PromptSignal(prompt=event.message))
            self.machine.get_app().add_user_message(event.message)
            from . import TuiWaitingState

            self.machine.change_state(TuiWaitingState(self.machine))
        else:
            self.machine.notify(
                f"Invalid input type: {event.input_type}", severity="error"
            )

    def handle_stop_behaviour_event(self, _: behaviour_event.StopEvent):
        self.machine.change_state(TuiStopState(self.machine))
