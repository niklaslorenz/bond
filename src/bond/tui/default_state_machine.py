import asyncio
from asyncio import Task, sleep
from multiprocessing.queues import Queue

from textual.notifications import SeverityLevel

from bond.behaviours.behaviour_event import BehaviourEvent
from bond.behaviours.behaviour_signal import BehaviourSignal
from bond.tui import ITuiState
from bond.tui.states.tui_pre_start_state import TuiPreStartState
from bond.tui.types import ITuiApp, ITuiEvent

from . import logger


class DefaultTuiStateMachine:
    tui_state: ITuiState
    _worker: Task | None = None

    def __init__(
        self,
        app: ITuiApp,
        signal_queue: Queue[BehaviourSignal],
        event_queue: Queue[BehaviourEvent | ITuiEvent],
    ):
        self.app = app
        self.signal_queue = signal_queue
        self.event_queue = event_queue

        self.tui_state = TuiPreStartState(self)

    def schedule_event(self, event: ITuiEvent | BehaviourEvent, *, millis: int):
        asyncio.create_task(self._wait_and_handle(event, millis))

    def handle_event(self, event: ITuiEvent | BehaviourEvent):
        self.event_queue.put(event)

    def change_state(self, destination: ITuiState):
        logger.debug(
            f"Changed state from {type(self.tui_state)} to {type(destination)}"
        )
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

    def stop(self):
        if self._worker is not None:
            self._worker.cancel()
        self.app.exit()

    def get_app(self) -> ITuiApp:
        return self.app

    def get_state(self) -> ITuiState:
        return self.tui_state

    async def _wait_and_handle(self, event: ITuiEvent | BehaviourEvent, millis: int):
        await sleep(millis / 1000)
        self.handle_event(event)

    async def _listen_to_events(self):
        try:
            while True:
                event = await asyncio.to_thread(self.event_queue.get)
                if isinstance(event, BehaviourEvent):
                    self.tui_state.handle_behaviour_event(event)
                else:
                    self.tui_state.handle_tui_event(event)
        except asyncio.CancelledError:
            return
