import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from returns.result import Failure, Result, Success
from textual.app import App, ComposeResult

from bond.behaviours.async_loop import AsyncAgentLoop
from bond.behaviours.types import LoopStatus
from bond.conversation.types import (
    TextChunk,
    UserConversationMessage,
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

    def __init__(
        self,
        loop: AsyncAgentLoop,
        event_handler: TuiEventHandler,
        save_on_quit: bool,
        user_name: str = "User",
    ):
        super().__init__()
        self.agent_loop = loop
        self._event_handler = event_handler
        self._user_name = user_name
        self._command_handler = TuiCommandHandler(self, save_on_quit)
        self.task_registry = TaskRegistry()
        self.popup_manager = PopupManager(self)
        self.chat_view = ChatView()
        self._action_lock = asyncio.Lock()
        self._chat_lock = asyncio.Lock()

        self.agent_loop.loop_status.subscribe(self._on_loop_status_update)

    @property
    def is_idle(self) -> bool:
        """
        Whether the agent loop is idle and waiting for an input.
        Note that this is only True, if the loop is actively waiting for an input.
        When the loop is paused, this is still False.
        """
        return self.agent_loop.is_idle

    @property
    def action_lock(self) -> asyncio.Lock:
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
        logger.debug("Exiting Bond TUI")
        try:
            if not self.is_idle:
                await self.agent_loop.cancel()
                logger.warning("Forcefully cancelled Agent Loop")
            self.popup_manager.close_all()
            await self._event_handler.stop()
            self.task_registry.clear()
            self.agent_loop.persona.release()
        finally:
            super().exit()

    async def run_async(self):
        logger.debug("Starting Bond TUI")
        await self.agent_loop.start()
        await super().run_async()

    def compose(self) -> ComposeResult:
        yield self.chat_view

    async def on_mount(self):
        self.chat_view.input_bar.focus()
        await self.chat_view.sync(self.agent_loop.conversation)
        self.chat_view.status_bar.set_persona(self.agent_loop.persona.name)
        self.chat_view.status_bar.set_status("Idle")
        self._event_handler.start()

    # Control

    async def stop(self, immediate: bool = False):
        logger.debug("Stopping Bond TUI")
        await self.agent_loop.stop(immediate)
        await self.exit()
        logger.debug("Stopped Bond TUI")

    def schedule[T](self, coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        return self.task_registry.register(coro)

    async def fix(self):
        logger.debug("Checking TUI for unexpected state...")
        if not self._event_handler.is_running():
            logger.info("Event Handler was not running. Restarting.")
            self._event_handler.start(None)
        if not self.agent_loop.is_running:
            logger.info("Agent loop was not running. Restarting.")
            await self.agent_loop.start()
        elif not self.agent_loop.is_idle:
            logger.info("Agent loop is busy. Interrupting")
            self.agent_loop.interrupt()
        self.task_registry.clear()
        self.popup_manager.close_all()

    def prompt(self, message: UserMessage) -> Result[None, str]:
        """
        Prompt a response from the agent loop.

        Returns:
            Success: If the prompt has been scheduled
            Failure: Reason for why the prompting failed
        """
        if not self.agent_loop.is_idle:
            return Failure("Agent is busy")
        logger.debug("Prompting agent")
        result = self.agent_loop.prompt(
            UserConversationMessage(message=message, name=self._user_name)
        )
        return result

    async def select_conversation(
        self, conversations: list[str]
    ) -> Result[str | None, None]:
        """
        Show the conversation selection popup.
        Wait for the popup to close and return the selected conversation name.

        Returns:
            Success[str | None]: The conversation name if the popup was opened and closed successfully
            Failure[None]: if the popup was not opened or cancelled
        """
        logger.debug("Selecting conversation")
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
        logger.debug("Asking confirmation")
        popup = ConfirmationPopup(prompt)
        self.popup_manager.show(popup)
        return (await popup.wait_for()).map(lambda x: x == True).value_or(False)

    # Event Handling

    async def on_input_bar_submitted(self, event: MultiLineInput.Submitted):
        text = event.value.strip()
        if text == "!fix":
            event.accept()
            await self.fix()
            return
        if text == "!stop":
            event.accept()
            if self.agent_loop.is_running and not self.is_idle:
                self.agent_loop.interrupt()
        if text == "!KILL":
            await self.exit()
        if text.startswith(":"):
            cmd = text[1:]
            if await self._command_handler(cmd):
                event.accept()
        elif not self.action_lock.locked():
            async with self._action_lock:
                result = self.prompt(UserMessage(content=[TextChunk(text=event.value)]))
                if isinstance(result, Success):
                    event.accept()
                else:
                    logger.debug(f"Failed to prompt agent: {result.failure()}")

    # Internals

    def _on_loop_status_update(self, status: LoopStatus):
        self.chat_view.status_bar.set_status(status)
