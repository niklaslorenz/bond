from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.widgets import Button, Static

from bond.tui.widgets.popup import TuiPopup


class ConfirmationPopup(TuiPopup[bool], Vertical):
    def __init__(
        self,
        request: str,
    ):
        super().__init__()
        self.accept_button = Button(
            "Accept", variant="success", id="confirmation-request-accept-button"
        )
        self.deny_button = Button(
            "Deny", variant="error", id="confirmation-request-deny-button"
        )

        self.request_field = Static(request)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirmation-request-accept-button":
            event.stop()
            self.finish(True)

        if event.button.id == "confirmation-request-deny-button":
            event.stop()
            self.finish(False)

    def compose(self):
        with ScrollableContainer():
            yield self.request_field
        with Horizontal(classes="button-bar"):
            yield self.deny_button
            yield self.accept_button
