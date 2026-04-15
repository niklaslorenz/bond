from dataclasses import dataclass

from bond.behaviours import behaviour_event
from bond.behaviours.behaviour_signal import StopSignal
from bond.tui import ITuiEvent, ITuiState, ITuiStateMachine
from bond.tui import event as tui_event


@dataclass
class TuiState:
    machine: ITuiStateMachine

    def handle_tui_event(self, event: ITuiEvent):
        handler = getattr(
            self,
            f"handle_{event.get_type()}_event",
            self.handle_invalid_tui_event,
        )
        handler(event)

    def handle_behaviour_event(self, event: behaviour_event.BehaviourEvent):
        handler = getattr(
            self,
            f"handle_{event.type}_behaviour_event",
            self.handle_invalid_behaviour_event,
        )
        handler(event)

    def on_enter(self, source: ITuiState):
        pass

    def on_exit(self, destination: ITuiState):
        pass

    def handle_invalid_tui_event(self, event: ITuiEvent):
        self.machine.notify(
            f"Invalid TUI Event: {event.get_type()} in state {type(self)}",
            severity="error",
        )

    def handle_invalid_behaviour_event(self, event: behaviour_event.BehaviourEvent):
        self.machine.notify(
            f"Invalid Behaviour Event: {event.type} in state {type(self)}",
            severity="error",
        )

    # Tui Events

    def handle_user_input_event(self, _: tui_event.UserInputEvent):
        pass

    def handle_stop_event(self, event: tui_event.StopEvent):
        if not event.immediately:
            from . import TuiWaitForStopState

            self.machine.send_signal(StopSignal())
            self.machine.change_state(TuiWaitForStopState(self.machine))
        else:
            from . import TuiStopState

            self.machine.change_state(TuiStopState(self.machine))

    # Behaviour Events

    def handle_error_behaviour_event(self, event: behaviour_event.ErrorEvent):
        self.machine.notify(
            f"Error in behaviour loop ({type(event)}): {event}", severity="error"
        )
        if event.critical:
            _ = self.machine.schedule_event(
                tui_event.StopEvent(immediately=True), millis=3000
            )

    def handle_stop_behaviour_event(self, _: behaviour_event.StopEvent):
        self.machine.notify(f"Behaviour loop exited unexpectedly", severity="error")
        self.machine.schedule_event(tui_event.StopEvent(immediately=True), millis=3000)

    def handle_notify_behaviour_event(self, event: behaviour_event.NotifyEvent):
        self.machine.notify(event.message)

    def handle_response_start_behaviour_event(
        self, event: behaviour_event.ResponseStartEvent
    ):
        self.machine.notify(
            f"Unexpected response start behaviour event in state {type(self)}",
            severity="warning",
        )
        msg = self.machine.get_app().add_assistant_message(
            event.author, None, None, True
        )

        from . import TuiReceivingState

        self.machine.change_state(TuiReceivingState(self.machine, msg))

    def handle_response_end_behaviour_event(self, _: behaviour_event.ResponseEndEvent):
        self.machine.notify(
            f"Unexpected response end behaviour event in state {type(self)}",
            severity="warning",
        )

        from . import TuiWaitingState

        self.machine.change_state(TuiWaitingState(self.machine))

    def handle_waiting_for_input_behaviour_event(
        self, _: behaviour_event.WaitingForInputEvent
    ):
        self.machine.notify(
            f"Unexpected waiting for input behaviour event in state {type(self)}",
            severity="warning",
        )

        from . import TuiIdleState

        self.machine.change_state(TuiIdleState(self.machine))

    def handle_append_message_chunk_behaviour_event(
        self, event: behaviour_event.AppendMessageChunkEvent
    ):
        self.machine.notify(
            f"Unexpected append message chunk behaviour event in state {type(self)}",
            severity="warning",
        )
        msg = self.machine.get_app().add_assistant_message(
            "<unknown>", None, None, True
        )

        from . import TuiReceivingState

        new_state = TuiReceivingState(self.machine, msg)
        self.machine.change_state(new_state)
        new_state.handle_behaviour_event(event)

    def handle_request_confirmation_behaviour_event(
        self, event: behaviour_event.RequestConfirmationEvent
    ):
        event.result().set_result(False)
        self.handle_invalid_behaviour_event(event)

    def handle_call_tool_behaviour_event(self, event: behaviour_event.CallToolEvent):
        self.machine.notify(
            f"Unexpected call tool behaviour event in state {type(self)}",
            severity="warning",
        )
        from . import TuiWaitingState

        new_state = TuiWaitingState(self.machine)
        self.machine.change_state(new_state)
        new_state.handle_behaviour_event(event)

    def handle_tool_return_behaviour_event(
        self, event: behaviour_event.ToolReturnEvent
    ):
        self.machine.notify(
            f"Unexpected tool return behaviour event in state {type(self)}",
            severity="warning",
        )
        block = self.machine.get_app().add_tool_call("<unknown>", True)
        block.append(event.result)
        from . import TuiWaitingState

        self.machine.change_state(TuiWaitingState(self.machine))

    def handle_change_persona_behaviour_event(
        self, event: behaviour_event.ChangePersonaEvent
    ):
        self.machine.notify(
            f"Unexpected change persona behaviour event in state {type(self)}",
            severity="warning",
        )
        self.machine.get_app().set_persona(event.name, event.provider)

    def handle_clear_chat_behaviour_event(self, _: behaviour_event.ClearChatEvent):
        self.machine.notify(
            f"Unexpected clear chat behaviour event in state {type(self)}",
            severity="warning",
        )
        self.machine.get_app().clear_chat()

    def handle_restore_conversation_behaviour_event(
        self, event: behaviour_event.RestoreConversationEvent
    ):
        self.machine.notify(
            f"Unexpected restore conversation behaviour event in state {type(self)}",
            severity="warning",
        )
        self.machine.get_app().synchronize(event.conversation)

    def handle_show_conversation_selector_behaviour_event(
        self, event: behaviour_event.ShowConversationSelectorEvent
    ):
        from . import TuiConversationSelectorState

        self.machine.change_state(
            TuiConversationSelectorState(self.machine, event.conversations)
        )
