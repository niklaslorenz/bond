import asyncio
from pathlib import Path
from queue import Queue
from typing import Literal

from textual.app import App, ComposeResult
from textual.worker import Worker

from bond.behaviours.behaviour_signal import (BehaviourSignal, CommandSignal,
                                              PromptSignal)
from bond.behaviours.loop import LoopBehaviour
from bond.conversation.conversation import Conversation
from bond.conversation.types import (AssistantMessageChunk, SystemMessageChunk,
                                     TextChunk, ThinkChunk)
from bond.io.queue_env import BehaviourEvent, StopEvent
from bond.persona import Persona
from bond.tui.widgets import (ChatLog, ChatMessage, InputBar, MultiLineInput,
                              StatusBar)


class BondTui(App):

    def __init__(
        self,
        signal_queue: Queue[BehaviourSignal],
        event_queue: Queue[BehaviourEvent],
        starting_persona: Persona,
    ):
        super().__init__()
        self.signal_queue = signal_queue
        self.event_queue = event_queue
        self.running_workers: list[Worker] = []
        self.messages: list[ChatMessage] = []
        self._current_open_message: ChatMessage | None = None
        self._last_assistant_message: ChatMessage | None = None
        self._allow_user_input = True

        self.status_bar = StatusBar(id="status-bar")
        self.status_bar.status = "Idle"
        self.status_bar.persona = starting_persona.name
        self.status_bar.provider = starting_persona.provider
        self.status_bar.context_length = 0
        self.chat_log = ChatLog()
        self.input_bar = InputBar(id="input-layer")

    CSS_PATH = str(Path(__file__).with_name("tui.css"))

    def compose(self) -> ComposeResult:
        yield self.chat_log
        yield self.status_bar
        yield self.input_bar

    def on_mount(self):
        self.running_workers.append(self.run_worker(self._listen_to_events))
        self.input_bar.focus()
        for message in self.messages:
            self.chat_log.add_message(message)
        self.chat_log.scroll_end(animate=False)

    def add_message(self, message: ChatMessage):
        self.messages.append(message)
        if self.chat_log.is_mounted:
            self.chat_log.add_message(message)
        if message.role == "assistant":
            self._last_assistant_message = message
        else:
            self._last_assistant_message = None
            self._current_open_message = None

    def clear_log(self):
        self._last_assistant_message = None
        self._current_open_message = None
        if self.chat_log.is_mounted:
            self.chat_log.remove_children()
        self.messages.clear()

    def synchronize(self, conversation: Conversation, length: int | None = None):
        self.clear_log()
        for message in conversation.history[-length if length is not None else 0 :]:
            if message.message.content is not None:
                self._handle_message_content(
                    message.message.content, message.message.role, message.author
                )
        if self.chat_log.is_mounted:
            self.chat_log.scroll_end(animate=False)

    def quit(self):
        self.event_queue.put(StopEvent())

    def link(self, beh: LoopBehaviour):
        self.beh = beh

    async def on_multi_line_input_submitted(self, event: MultiLineInput.Submitted):
        if not self._allow_user_input:
            return

        text = event.value.strip()
        event.clear_field()

        if text.startswith(":"):
            cmd = text[1:]
            self.signal_queue.put(CommandSignal(command=cmd))
        else:
            self.add_message(ChatMessage.create_user_msg("User", text))
            self._allow_user_input = False
            self.status_bar.status = "Waiting"
            self.signal_queue.put(PromptSignal(prompt=text))
        self.chat_log.scroll_end()

    async def _listen_to_events(self):
        try:
            while True:
                event = await asyncio.to_thread(self.event_queue.get)
                if event.type == "stop":
                    for worker in self.running_workers:
                        worker.cancel()
                    self.exit()
                    break
                self._handle_event(event)
        except asyncio.CancelledError:
            return

    def _handle_event(self, event: BehaviourEvent):
        if event.type == "notify":
            self.notify(event.message)
        elif event.type == "stream_start":
            self._ensure_open_message(event.agent_name, overwrite=False)
            self.status_bar.status = "Responding"
        elif event.type == "stream_end":
            self._last_assistant_message = self._current_open_message
            self._current_open_message = None
            self._allow_user_input = True
            self.status_bar.status = "Idle"
        elif event.type == "stream_chunk":
            if event.chunk.choices[0].delta.content is not None:
                self._handle_message_content(
                    event.chunk.choices[0].delta.content, "assistant", None
                )
            self.chat_log.scroll_end()
        elif event.type == "completion_response":
            if event.response.choices[0].message.content is not None:
                self._handle_message_content(
                    event.response.choices[0].message.content, "assistant", None
                )
        elif event.type == "confirmation_request":
            # TODO: implement
            event._value.set_result(False)
        elif event.type == "tool_call_result":
            msg = self._current_open_message or self._last_assistant_message
            if msg is not None:
                msg.append_tool_result(
                    event.tool_return, f"Tool: {event.tool_call.function.name}"
                )
            else:
                self.notify(
                    f"Could not assign tool return to a caller message",
                    severity="error",
                )
        elif event.type == "update_persona":
            self.status_bar.persona = event.persona_name
            self.status_bar.provider = event.provider_name
        elif event.type == "clear_log":
            self.clear_log()
        elif event.type == "sync_log":
            self.synchronize(event.conversation, event.message_count)
        elif event.type == "block":
            self._allow_user_input = False
        elif event.type == "release":
            self._allow_user_input = True
        else:
            self.notify(f"Invalid event type: {event.type}", severity="error")

    def _ensure_open_message(self, author: str | None, overwrite: bool) -> ChatMessage:
        if self._current_open_message is None or overwrite:
            if self._last_assistant_message is not None:
                self._current_open_message = self._last_assistant_message
            else:
                self._current_open_message = ChatMessage(
                    author or "Assistant", "assistant"
                )
                self.add_message(self._current_open_message)
        return self._current_open_message

    def _handle_message_content(
        self,
        content: list[AssistantMessageChunk] | list[SystemMessageChunk],
        role: Literal["user", "tool", "assistant", "system"],
        author: str | None,
    ):
        if role == "tool":
            msg = self._ensure_open_message(author, overwrite=False)
            msg.append_tool_result(
                " ".join([c.text for c in content if isinstance(c, TextChunk)]),
                name=author,
            )
        elif role == "assistant":
            msg = self._ensure_open_message(author, overwrite=False)
            self._handle_message_chunks(msg, content)
        elif role == "system":
            msg = ChatMessage(author or "System", role)
            self._handle_message_chunks(msg, content)
            self.add_message(msg)
        elif role == "user":
            msg = ChatMessage(author or "User", role)
            self._handle_message_chunks(msg, content)
            self.add_message(msg)

    def _handle_message_chunks(
        self,
        msg: ChatMessage,
        content: list[AssistantMessageChunk] | list[SystemMessageChunk],
    ):
        for content_chunk in content:
            if isinstance(content_chunk, TextChunk):
                msg.append_text(content_chunk.text)
            if isinstance(content_chunk, ThinkChunk):
                for think_chunk in content_chunk.thinking:
                    if isinstance(think_chunk, TextChunk):
                        msg.append_thinking(think_chunk.text)
