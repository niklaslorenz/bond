"""TUI State Machine module."""

import asyncio
from asyncio import sleep
from concurrent.futures import Future
from dataclasses import dataclass
from multiprocessing import Queue
from typing import TYPE_CHECKING, Literal

from textual.notifications import SeverityLevel
from textual.worker import Worker

from bond.behaviours import behaviour_event
from bond.behaviours.behaviour_event import BehaviourEvent
from bond.behaviours.behaviour_signal import (BehaviourSignal, CommandSignal,
                                              PromptSignal, StopSignal)
from bond.tui.state.tui_event import (RequestConfirmEvent, StopEvent, TuiEvent,
                                      UserInputEvent)
from bond.tui.widgets import ChatMessage, ToolResultBlock

if TYPE_CHECKING:
    from bond.tui.app import BondTui

TuiStatus = Literal["Idle", "Waiting", "Receiving", "Tool Call"]


@dataclass
class TuiState:
    machine: "TuiStateMachine"

    def handle_tui_event(self, event: TuiEvent):
        handler = getattr(
            self, f"handle_{event.type}_event", self.machine.handle_invalid_tui_event
        )
        handler(event)

    def handle_behaviour_event(self, event: BehaviourEvent):
        handler = getattr(
            self,
            f"handle_{event.type}_behaviour_event",
            self.machine.handle_invalid_behaviour_event,
        )
        handler(event)

    def on_enter(self, source: "TuiState"):
        pass

    def on_exit(self, destination: "TuiState"):
        pass

    # Tui Events

    def handle_user_input_event(self, event: UserInputEvent):
        event.set_cancelled()

    def handle_stop_event(self, event: StopEvent):
        if not event.immediately:
            self.machine.change_state(TuiWaitForStopState(self.machine))
            self.machine.send_signal(StopSignal())
        else:
            self.machine.change_state(TuiStopState(self.machine))

    def handle_request_confirm_event(self, event: RequestConfirmEvent):
        self.machine.notify(
            f"Unexpected request confirmation event in state {type(self)}",
            severity="warning",
        )

    # Behaviour Events

    def handle_error_behaviour_event(self, event: behaviour_event.ErrorEvent):
        self.machine.notify(
            f"Error in behaviour loop ({type(event)}): {event}", severity="error"
        )
        if event.critical:
            _ = self.machine.schedule_tui_event(
                StopEvent(immediately=True), millis=3000
            )

    def handle_stop_behaviour_event(self, event: behaviour_event.StopEvent):
        self.machine.notify(f"Behaviour loop exited unexpectedly", severity="error")
        _ = self.machine.schedule_tui_event(StopEvent(immediately=True), millis=3000)

    def handle_notify_behaviour_event(self, event: behaviour_event.NotifyEvent):
        self.machine.notify(event.message)

    def handle_response_start_behaviour_event(
        self, event: behaviour_event.ResponseStartEvent
    ):
        self.machine.notify(
            f"Unexpected response start behaviour event in state {type(self)}",
            severity="warning",
        )
        msg = self.machine.app.add_assistant_message(event.author, None, None, True)
        self.machine.change_state(TuiReceivingState(self.machine, msg))

    def handle_response_end_behaviour_event(
        self, event: behaviour_event.ResponseEndEvent
    ):
        self.machine.notify(
            f"Unexpected response end behaviour event in state {type(self)}",
            severity="warning",
        )
        self.machine.change_state(TuiWaitingState(self.machine))

    def handle_waiting_for_input_behaviour_event(
        self, event: behaviour_event.WaitingForInputEvent
    ):
        self.machine.notify(
            f"Unexpected waiting for input behaviour event in state {type(self)}",
            severity="warning",
        )
        self.machine.change_state(TuiIdleState(self.machine))

    def handle_append_message_chunk_behaviour_event(
        self, event: behaviour_event.AppendMessageChunkEvent
    ):
        self.machine.notify(
            f"Unexpected append message chunk behaviour event in state {type(self)}",
            severity="warning",
        )
        msg = self.machine.app.add_assistant_message("<unknown>", None, None, True)
        new_state = TuiReceivingState(self.machine, msg)
        self.machine.change_state(new_state)
        new_state.handle_behaviour_event(event)

    def handle_request_confirmation_behaviour_event(
        self, event: behaviour_event.RequestConfirmationEvent
    ):
        self.machine.change_state(
            TuiWaitForConfirmationResponseState(
                self.machine, self, event.request, event.result
            )
        )

    def handle_call_tool_behaviour_event(self, event: behaviour_event.CallToolEvent):
        self.machine.notify(
            f"Unexpected call tool behaviour event in state {type(self)}",
            severity="warning",
        )
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
        block = self.machine.app.add_tool_call("<unknown>", True)
        block.append(event.result)
        self.machine.change_state(TuiWaitingState(self.machine))

    def handle_change_persona_behaviour_event(
        self, event: behaviour_event.ChangePersonaEvent
    ):
        self.machine.notify(
            f"Unexpected change persona behaviour event in state {type(self)}",
            severity="warning",
        )
        self.machine.app.set_persona(event.name)

    def handle_clear_chat_behaviour_event(self, event: behaviour_event.ClearChatEvent):
        self.machine.notify(
            f"Unexpected clear chat behaviour event in state {type(self)}",
            severity="warning",
        )
        self.machine.app.clear_chat()

    def handle_restore_conversation_behaviour_event(
        self, event: behaviour_event.RestoreConversationEvent
    ):
        self.machine.notify(
            f"Unexpected restore conversation behaviour event in state {type(self)}",
            severity="warning",
        )
        self.machine.app.synchronize(event.conversation)


@dataclass
class TuiStartState(TuiState):
    def on_exit(self, destination: TuiState):
        self.machine.app.set_persona(self.machine.persona_name)


@dataclass
class TuiStopState(TuiState):
    def on_enter(self, source: TuiState):
        self.machine.stop()


@dataclass
class TuiIdleState(TuiState):
    def handle_user_input_event(self, event: UserInputEvent):
        event.set_cancelled(False)
        if event.input_type == "command":
            self.machine.send_signal(CommandSignal(command=event.message))
            self.machine.change_state(TuiWaitForCommandResponseState(self.machine))
        elif event.input_type == "prompt":
            self.machine.send_signal(PromptSignal(prompt=event.message))
            self.machine.change_state(TuiWaitingState(self.machine))
            self.machine.app.add_user_message(event.message)
        else:
            self.machine.notify(
                f"Invalid input type: {event.input_type}", severity="error"
            )


@dataclass
class TuiReceivingState(TuiState):
    msg: ChatMessage

    def __init__(self, machine: "TuiStateMachine", msg: ChatMessage):
        super().__init__(machine)
        self.msg = msg

    def on_enter(self, source: TuiState):
        self.machine.app.set_status("Receiving")

    def handle_response_end_behaviour_event(
        self, event: behaviour_event.ResponseEndEvent
    ):
        self.machine.change_state(TuiWaitingState(self.machine))

    def handle_append_message_chunk_behaviour_event(
        self, event: behaviour_event.AppendMessageChunkEvent
    ):
        text, think = event.chunk.extract_content()
        if think is not None:
            self.msg.append_thinking(think)
        if text is not None:
            self.msg.append_text(text)


@dataclass
class TuiWaitingState(TuiState):
    def on_enter(self, source: TuiState):
        self.machine.app.set_status("Waiting")

    def handle_response_start_behaviour_event(
        self, event: behaviour_event.ResponseStartEvent
    ):
        msg = self.machine.app.add_assistant_message(event.author, None, None, True)
        self.machine.change_state(TuiReceivingState(self.machine, msg))

    def handle_waiting_for_input_behaviour_event(
        self, event: behaviour_event.WaitingForInputEvent
    ):
        self.machine.change_state(TuiIdleState(self.machine))

    def handle_call_tool_behaviour_event(self, event: behaviour_event.CallToolEvent):
        block = self.machine.app.add_tool_call(event.call.function.name, True)
        self.machine.change_state(TuiWaitForToolResultState(self.machine, block))

    def handle_change_persona_behaviour_event(
        self, event: behaviour_event.ChangePersonaEvent
    ):
        self.machine.app.set_persona(event.name)

    def handle_clear_chat_behaviour_event(self, event: behaviour_event.ClearChatEvent):
        self.machine.app.clear_chat()

    def handle_restore_conversation_behaviour_event(
        self, event: behaviour_event.RestoreConversationEvent
    ):
        self.machine.app.synchronize(event.conversation)


@dataclass
class TuiWaitForToolResultState(TuiState):
    block: ToolResultBlock

    def __init__(self, machine: "TuiStateMachine", block: ToolResultBlock):
        super().__init__(machine)
        self.block = block

    def on_enter(self, source: TuiState):
        self.machine.app.set_status("Tool Call")

    def handle_tool_return_behaviour_event(
        self, event: behaviour_event.ToolReturnEvent
    ):
        self.block.append(event.result)
        self.machine.change_state(TuiWaitingState(self.machine))


@dataclass
class TuiWaitForCommandResponseState(TuiState):
    def on_enter(self, source: "TuiState"):
        self.machine.app.set_status("Waiting")


@dataclass
class TuiWaitForStopState(TuiState):
    def handle_stop_behaviour_event(self, event: behaviour_event.StopEvent):
        self.machine.change_state(TuiStopState(self.machine))


class TuiWaitForConfirmationResponseState(TuiState):
    previous_state: TuiState
    request: str
    result: Future[bool]

    def __init__(
        self,
        machine: "TuiStateMachine",
        previous_state: TuiState,
        request: str,
        result: Future[bool],
    ):
        super().__init__(machine)
        self.previous_state = previous_state
        self.request = request
        self.result = result

    def on_enter(self):
        self.machine.app.open_confirmation_prompt(self.request)

    def handle_request_confirm_event(self, event: RequestConfirmEvent):
        self.result.set_result(event.accepted)
        self.machine.change_state(self.previous_state)


class TuiStateMachine:
    tui_state: TuiState
    app: BondTui
    persona_name: str
    behaviour_event_queue: Queue[BehaviourEvent]
    _worker: Worker | None

    def __init__(
        self,
        signal_queue: Queue[BehaviourSignal],
        behaviour_event_queue: Queue[BehaviourEvent],
        persona_name: str,
    ):
        self.signal_queue = signal_queue
        self.behaviour_event_queue = behaviour_event_queue
        self.persona_name = persona_name

        self.state = TuiStartState(self)
        self.change_state(TuiIdleState(self))

    async def schedule_tui_event(self, event: TuiEvent, millis: int):
        await sleep(1000 * millis)
        self.handle_tui_event(event)

    def handle_tui_event(self, event: TuiEvent):
        self.tui_state.handle_tui_event(event)

    def handle_behaviour_event(self, event: BehaviourEvent):
        self.tui_state.handle_behaviour_event(event)

    def change_state(self, destination: TuiState):
        self.tui_state.on_exit(destination)
        old = self.tui_state
        self.tui_state = destination
        destination.on_enter(old)

    def send_signal(self, signal: BehaviourSignal):
        self.signal_queue.put(signal)

    def notify(
        self, message: str, title: str = "", severity: SeverityLevel = "information"
    ):
        self.app.notify(message, title=title, severity=severity)

    def run(self, app: BondTui):
        self.app = app
        if self._worker is not None:
            raise RuntimeError("worker is already defined")
        _worker = self.app.run_worker(self._listen_to_events)

    async def _listen_to_events(self):
        try:
            while True:
                event = await asyncio.to_thread(self.behaviour_event_queue.get)
                self.handle_behaviour_event(event)
        except asyncio.CancelledError:
            return

    def stop(self):
        if self._worker is not None:
            self._worker.cancel()
        self.app.exit()

    def handle_invalid_tui_event(self, event: TuiEvent):
        self.notify(f"Invalid TUI Event: {event.type}", severity="error")

    def handle_invalid_behaviour_event(self, event: BehaviourEvent):
        self.notify(f"Invalid Behaviour Event: {event.type}", severity="error")
