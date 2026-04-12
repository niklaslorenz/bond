import asyncio
from asyncio import Task, sleep
from multiprocessing import Queue

from textual.notifications import SeverityLevel

from bond.behaviours.behaviour_event import BehaviourEvent
from bond.behaviours.behaviour_signal import BehaviourSignal
from bond.tui import ITuiState
from bond.tui.states import TuiIdleState, TuiStartState
from bond.tui.types import ITuiApp, ITuiEvent


class DefaultTuiStateMachine:
    tui_state: ITuiState
    app: ITuiApp
    persona_name: str
    behaviour_event_queue: Queue
    _worker: Task | None = None

    def __init__(
        self,
        app: ITuiApp,
        signal_queue: Queue,
        behaviour_event_queue: Queue,
        persona_name: str,
    ):
        self.signal_queue = signal_queue
        self.behaviour_event_queue = behaviour_event_queue
        self.persona_name = persona_name

        self.state = TuiStartState(self, persona_name)
        self.change_state(TuiIdleState(self))

    async def schedule_tui_event(self, event: ITuiEvent, *, millis: int):
        await sleep(1000 * millis)
        self.handle_tui_event(event)

    def handle_tui_event(self, event: ITuiEvent):
        self.tui_state.handle_tui_event(event)

    def handle_behaviour_event(self, event: BehaviourEvent):
        self.tui_state.handle_behaviour_event(event)

    def change_state(self, destination: ITuiState):
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

    def run(self):
        if self._worker is not None:
            raise RuntimeError("worker is already defined")
        self._worker = asyncio.create_task(self._listen_to_events())

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

    def get_app(self) -> ITuiApp:
        return self.app

    def handle_invalid_tui_event(self, event: ITuiEvent):
        self.notify(f"Invalid TUI Event: {event.get_type()}", severity="error")

    def handle_invalid_behaviour_event(self, event: BehaviourEvent):
        self.notify(f"Invalid Behaviour Event: {event.type}", severity="error")
