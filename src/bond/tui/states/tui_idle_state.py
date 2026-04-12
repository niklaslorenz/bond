from dataclasses import dataclass

from bond.behaviours.behaviour_signal import CommandSignal, PromptSignal
from bond.tui.event import UserInputEvent
from bond.tui.states.tui_state import TuiState


@dataclass
class TuiIdleState(TuiState):
    def handle_user_input_event(self, event: UserInputEvent):
        event.set_cancelled(False)
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
