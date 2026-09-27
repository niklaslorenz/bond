import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from returns.result import Failure, Result
from textual.app import App, ComposeResult

from bond.behaviours.async_loop import AsyncAgentLoop
from bond.conversation.types import (
    TextChunk,
    UserMessage,
)
from bond.tui.command_handler import TuiCommandHandler
from bond.tui.event_handler import TuiEventHandler
from bond.tui.task_registry import TaskRegistry
from bond.tui.widgets.chat_view import ChatView
from bond.tui.widgets.confirmation_popup import ConfirmationPopup
from bond.tui.widgets.conversation_selector_popup import ConversationSelectorPopup
from bond.tui.widgets.input_bar import MultiLineInput
from bond.tui.widgets.popup import PopupManager

from . import logger


class BondTui(App):

    CSS_PATH = str(Path(__file__).with_name("tui.css"))

    def __init__(self, loop: AsyncAgentLoop, event_handler: TuiEventHandler):
        super().__init__()
        self.agent_loop = loop
        self._event_handler = event_handler
        self._command_handler = TuiCommandHandler(self)
        self.task_registry = TaskRegistry()
        self.popup_manager = PopupManager(self)
        self.chat_view = ChatView()
        self._action_lock = asyncio.Lock()

    @property
    def chat_lock(self):
        """
        Lock for the chat state. Use this for processes that change
        the conversation state or the state of the agent loop.
        This lock is also used by the agent loop itself, so it can
        be used to prevent changes to be made while the loop is running.
        """
        return self.agent_loop.lock

    @property
    def action_lock(self):
        """
        Lock for actions triggered by the user that should be atomic.
        Use this to make sure a user interaction is completed before
        another one can be processed.
        """
        return self._action_lock

    @property
    def current_conversation(self):
        return self.agent_loop.conversation

    async def exit(self):
        logger.debug("Stopping Bond TUI")
        if self.chat_lock.locked():
            await self.agent_loop.cancel()
        self.popup_manager.close_all()
        await self._event_handler.stop()
        super().exit()

    async def run_async(self):
        logger.debug("Starting Bond TUI")
        await super().run_async()

    def compose(self) -> ComposeResult:
        yield self.chat_view

    async def on_mount(self):
        self.chat_view.input_bar.focus()
        await self.chat_view.sync(self.agent_loop.conversation)
        self.chat_view.status_bar.set_persona(
            self.agent_loop.persona.name, self.agent_loop.persona.provider
        )
        self.chat_view.status_bar.set_status("Idle")
        self._event_handler.start()

    # Control

    def schedule[T](self, coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        return self.task_registry.register(coro)

    def fix(self):
        logger.debug("Checking TUI for unexpected state...")
        if not self._event_handler.is_running():
            logger.info("Event Handler was not running. Restarting.")
            self._event_handler.start(None)
        self.task_registry.clear()
        self.popup_manager.close_all()

    def trigger_prompt(self, message: UserMessage) -> bool:
        """
        Trigger the agent loop to prompt a response if the chat is not currently locked.
        Return immediately after the task has been scheduled and
        do not wait for the task to complete.

        Returns:
            bool: whether the task has been scheduled
        """
        logger.debug("Triggered prompting")
        if self.chat_lock.locked():
            logger.debug("chat locked, aborting.")
            return False
        logger.debug("scheduling prompt task")
        self.schedule(self.prompt(message, False))
        return True

    async def prompt(self, message: UserMessage, fail_if_locked: bool) -> bool:
        """
        Prompt a response from the agent loop.
        If fail_if_locked is set and the chat is currently locked,
        immediately return a failure without prompting the response.
        Wait for the response to be complete and return.

        Returns:
            bool: if the prompt has been scheduled
        """
        if self.chat_lock.locked() and fail_if_locked:
            return False
        self.chat_view.status_bar.set_status("Waiting")
        await self.agent_loop.prompt(message)
        self.chat_view.status_bar.set_status("Idle")
        return True

    def trigger_select_conversation(self, conversations: list[str]) -> bool:
        """
        Trigger the conversation selection popup if the chat is not currently locked.
        Return immediately after the task has been scheduled and
        do not wait for the task to complete.
        """
        if self.chat_lock.locked():
            return False
        self.schedule(self.select_conversation(conversations, False))
        return True

    async def select_conversation(
        self, conversations: list[str], fail_if_locked: bool
    ) -> Result[str | None, None]:
        """
        Show the conversation selection popup.
        If fail_if_locked is set and the chat is currently locked,
        immediately return a failure without opening the popup.
        Wait for the popup to close and return the selected conversation name.

        Returns:
            Success[str | None]: The conversation name if the popup was opened and closed successfully
            Failure[None]: if the popup was not opened or cancelled
        """
        logger.debug("Selecting conversation")
        if self.chat_lock.locked() and fail_if_locked:
            return Failure(None)

        async with self.chat_lock:
            popup = ConversationSelectorPopup(conversations)
            self.popup_manager.show(popup)

            result = await popup.wait_for()
            logger.debug(f"Selected conversation: {result}")
            return result

    async def ask_confirmation(self, prompt: str) -> bool:
        """
        Show the confirmation popup.
        Wait for the popup to close and return whether the request was accepted or not.
        If the popup gets cancelled, the request is considered denied.
        """
        popup = ConfirmationPopup(prompt)
        self.popup_manager.show(popup)
        return (await popup.wait_for()).map(lambda x: x == True).value_or(False)

    # Event Handling

    async def on_input_bar_submitted(self, event: MultiLineInput.Submitted):
        logger.debug("Input submitted")
        text = event.value.strip()
        if text == "!fix":
            event.accept()
            self.fix()
            return

        if text.startswith(":"):
            cmd = text[1:]
            logger.debug("Submitted command")
            if await self._command_handler(cmd):
                event.accept()
        elif not self.action_lock.locked():
            logger.debug("Aquiring Action lock")
            async with self._action_lock:
                logger.debug("Triggering prompt")
                if self.trigger_prompt(
                    UserMessage(content=[TextChunk(text=event.value)])
                ):
                    logger.debug("prompt triggering successful")
                    event.accept()
                    logger.debug("accepted event")
