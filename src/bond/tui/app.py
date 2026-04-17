from pathlib import Path

from textual.app import App, ComposeResult
from textual.notifications import SeverityLevel

from bond.conversation.conversation import Conversation
from bond.conversation.types import (AssistantMessageChunk, SystemMessageChunk,
                                     TextChunk, ThinkChunk)
from bond.tui.event import (ConversationSelectedEvent, RequestConfirmEvent,
                            StopEvent, UserInputEvent)
from bond.tui.types import ITuiStateMachine, TuiStatus
from bond.tui.widgets import (ChatLog, ChatMessage, ConfirmationPopup,
                              ConversationSelectorPopup, InputBar,
                              MultiLineInput, OverlayContainer, StatusBar,
                              ToolResultBlock)

from . import logger


class BondTui(App):
    state_machine: ITuiStateMachine
    popup: OverlayContainer | None

    def __init__(self, state_machine: ITuiStateMachine):
        super().__init__()
        self.state_machine = state_machine
        self.popup = None

        self.messages: list[ChatMessage] = []
        self.status_bar = StatusBar(
            status="<unknown>",
            persona="<unknown>",
            provider="<unknown>",
            context_length=0,
        )
        self.chat_log = ChatLog()
        self.input_bar = InputBar(id="input-layer")

    CSS_PATH = str(Path(__file__).with_name("tui.css"))

    def notify(
        self, message: str, *, title: str = "", severity: SeverityLevel = "information"
    ):
        if severity == "error":
            log = logger.error
        elif severity == "warning":
            log = logger.warning
        else:
            log = logger.info
        log(f"Notification: {message}")
        super().notify(message, title=title, severity=severity)

    def exit_tui(self):
        logger.info("Stopping Bond TUI")
        self.exit()

    async def start_tui(self):
        logger.info("Starting Bond TUI")
        await super().run_async()

    def compose(self) -> ComposeResult:
        yield self.chat_log
        yield self.status_bar
        yield self.input_bar

    def on_mount(self):
        self.input_bar.focus()
        for message in self.messages:
            self.chat_log.add_message(message)
        self.scroll_to_end()

    async def on_multi_line_input_submitted(self, event: MultiLineInput.Submitted):
        text = event.value.strip()
        if text.startswith(":"):
            cmd = text[1:]
            user_event = UserInputEvent(input_type="command", message=cmd)
        else:
            user_event = UserInputEvent(input_type="prompt", message=event.value)

        self.state_machine.handle_event(user_event)

    def clear_input(self):
        self.input_bar.input_field.clear()

    def add_message(self, message: ChatMessage):
        self.messages.append(message)
        if self.chat_log.is_mounted:
            self.chat_log.add_message(message)

    def add_user_message(self, text: str) -> ChatMessage:
        msg = ChatMessage.create_user_msg("User", text)
        self.add_message(msg)
        self.scroll_to_end()
        return msg

    def add_assistant_message(
        self, author: str, text: str | None, thinking: str | None, merge: bool
    ) -> ChatMessage:
        msg = self._get_current_assistant_message() if merge else None
        if msg is None:
            msg = ChatMessage(author=author, role="assistant")
            self.add_message(msg)
        if text is not None:
            msg.append_text(text)
        if thinking is not None:
            msg.append_thinking(thinking)
        return msg

    def add_system_message(self, author: str, text: str | None):
        msg = ChatMessage(author, role="system")
        self.add_message(msg)
        if text:
            msg.append_text(text)
        return msg

    def add_tool_call(self, function_name: str, merge: bool) -> ToolResultBlock:
        msg = self._get_current_assistant_message() if merge else None
        if msg is None:
            msg = ChatMessage(author=self.status_bar.persona, role="assistant")
            self.add_message(msg)
        block = msg.add_tool_result_block("", function_name)
        return block

    def set_status(self, status: TuiStatus):
        self.status_bar.status = status

    def set_persona(self, persona_name: str, provider: str):
        self.status_bar.persona = persona_name
        self.status_bar.provider = provider

    def stop(self):
        self.state_machine.handle_event(StopEvent(immediately=False))

    def open_confirmation_prompt(self, request: str):
        if self.popup is not None:
            msg = (
                "Could not open conversation selector, another popup is already opened"
            )
            logger.error(msg)
            self.notify(msg, severity="error")
            return
        popup = ConfirmationPopup(
            request,
            on_accept=lambda: self.state_machine.handle_event(
                RequestConfirmEvent(accepted=True)
            ),
            on_deny=lambda: self.state_machine.handle_event(
                RequestConfirmEvent(accepted=False)
            ),
        )
        overlay = OverlayContainer(popup)
        self.popup = overlay
        self.call_later(self.mount, overlay)

    def open_conversation_selector(self, conversations: list[str]):
        if self.popup is not None:
            msg = (
                "Could not open conversation selector, another popup is already opened"
            )
            logger.error(msg)
            self.notify(msg, severity="error")
            return
        popup = ConversationSelectorPopup(
            conversations,
            on_select=lambda name: self.state_machine.handle_event(
                ConversationSelectedEvent(name=name)
            ),
            on_cancel=lambda: self.state_machine.handle_event(
                ConversationSelectedEvent(name=None)
            ),
        )
        overlay = OverlayContainer(popup)
        self.popup = overlay
        self.call_later(self.mount, overlay)

    def close_popup(self):
        if self.popup is not None and self.popup.is_mounted:
            self.call_later(self.popup.remove)
        self.popup = None

    def clear_chat(self):
        if self.chat_log.is_mounted:
            self.chat_log.remove_children()
        self.messages.clear()

    def scroll_to_end(self):
        if self.chat_log.is_mounted:
            self.chat_log.scroll_end(animate=False)

    def scroll_message_to_top(self, msg: ChatMessage):
        if self.chat_log.is_mounted:
            self.chat_log.scroll_to_widget(msg, animate=False, top=True, force=True)

    def synchronize(self, conversation: Conversation, length: int | None = None):

        self.clear_chat()
        for message in conversation.history[-length if length is not None else 0 :]:
            if message.message.content is None:
                continue
            if message.message.role == "tool":
                text, _ = self._handle_message_chunks(message.message.content)
                block = self.add_tool_call(message.message.name or "Tool", merge=True)
                block.append(text or "")
            elif message.message.role == "assistant":
                text, thinking = self._handle_message_chunks(message.message.content)
                self.add_assistant_message(
                    message.author or "Assistant",
                    text=text,
                    thinking=thinking,
                    merge=True,
                )
            elif message.message.role == "system":
                text, _ = self._handle_message_chunks(message.message.content)
                self.add_system_message(message.author or "System", text=text)
            elif message.message.role == "user":
                text, _ = self._handle_message_chunks(message.message.content)
                self.add_user_message(text or "")

        if self.chat_log.is_mounted:
            self.scroll_to_end()

    def _get_current_assistant_message(self) -> ChatMessage | None:
        return (
            self.messages[-1]
            if len(self.messages) > 0 and self.messages[-1].role == "assistant"
            else None
        )

    def _handle_message_chunks(
        self,
        content: list[AssistantMessageChunk] | list[SystemMessageChunk],
    ) -> tuple[str | None, str | None]:
        text = []
        thinking = []
        for content_chunk in content:
            if isinstance(content_chunk, TextChunk):
                text.append(content_chunk.text)
            if isinstance(content_chunk, ThinkChunk):
                for think_chunk in content_chunk.thinking:
                    if isinstance(think_chunk, TextChunk):
                        thinking.append(think_chunk.text)
        return "".join(text) if len(text) > 0 else None, (
            "".join(thinking) if len(thinking) > 0 else None
        )
