import asyncio
from typing import TYPE_CHECKING

from returns.result import Failure, Result, Success
from textual.screen import ModalScreen

if TYPE_CHECKING:
    from bond.tui.app import BondTui


class TuiPopup[T](ModalScreen):
    def __init__(self):
        super().__init__()
        self.result: T | None = None
        self._was_cancelled: bool = False
        self._finished_event = asyncio.Event()
        self._manager: "PopupManager | None" = None

    def _register(self, manager: "PopupManager"):
        self._manager = manager

    def _release(self):
        self._manager = None

    async def wait_for(self) -> Result[T | None, None]:
        await self._finished_event.wait()
        if self._was_cancelled:
            return Failure(None)
        return Success(self.result)

    def finish(self, result: T | None):
        self.result = result
        self._finished_event.set()
        self.dismiss()

    def cancel(self):
        self.dismiss()

    def dismiss(self):
        if not self._finished_event.is_set():
            self._was_cancelled = True
            self._finished_event.set()
        if self._manager is not None:
            self._manager._dismiss(self)
        else:
            super().dismiss()


class PopupManager:
    def __init__(self, app: "BondTui"):
        self._app = app
        self._popups: list[TuiPopup] = []

    def show(self, popup: TuiPopup) -> None:
        self._popups.append(popup)
        popup._register(self)
        self._app.push_screen(popup)

    def _dismiss(self, popup: TuiPopup):
        if popup in self._popups:
            self._popups.remove(popup)
            popup._release()
            popup.dismiss()

    def close(self, popup: TuiPopup) -> None:
        if popup in self._popups:
            popup._release()
            popup.dismiss()

    def close_all(self) -> None:
        popups = self._popups.copy()
        self._popups.clear()
        for popup in reversed(popups):
            popup._release()
            popup.dismiss()
