import asyncio
from pathlib import Path
from queue import Queue

from textual.app import App, ComposeResult
from textual.worker import Worker

from bond.behaviours.behaviour_signal import (BehaviourSignal, CommandSignal,
                                              PromptSignal, StopSignal)
from bond.behaviours.loop import LoopBehaviour
from bond.conversation.types import (AssistantMessageChunk, TextChunk,
                                     ThinkChunk)
from bond.io.queue_env import BehaviourEvent, StopEvent
from bond.tui.widgets import (ChatLog, ChatMessage, InputBar, MultiLineInput,
                              StatusBar)


class BondTui(App):

    def __init__(
        self,
        signal_queue: Queue[BehaviourSignal],
        event_queue: Queue[BehaviourEvent],
    ):
        super().__init__()
        self.signal_queue = signal_queue
        self.event_queue = event_queue
        self.running_workers: list[Worker] = []
        self.messages: list[ChatMessage] = []
        self._current_open_message: ChatMessage | None = None
        self._last_assistant_message: ChatMessage | None = None

    CSS_PATH = str(Path(__file__).with_name("tui.css"))

    def compose(self) -> ComposeResult:
        self.chat_log = ChatLog()
        yield self.chat_log

        self.status_bar = StatusBar(id="status-bar")
        yield self.status_bar

        self.input_bar = InputBar(id="input-layer")
        yield self.input_bar

    def on_mount(self):
        self.running_workers.append(self.run_worker(self._listen_to_events))
        self.input_bar.focus()

    def add_message(self, message: ChatMessage):
        self.messages.append(message)
        self.chat_log.add_message(message)

    def quit(self):
        self.event_queue.put(StopEvent())

    def link(self, beh: LoopBehaviour):
        self.beh = beh

    async def on_multi_line_input_submitted(self, event: MultiLineInput.Submitted):
        text = event.value.strip()

        if text == ":quit" or text == ":q":
            self.signal_queue.put(StopSignal())
            self.quit()
            return

        if text.startswith(":"):
            cmd = text[1:]
            self.add_message(ChatMessage.create_command_msg(cmd))
            self.signal_queue.put(CommandSignal(command=cmd))
        else:
            self.add_message(ChatMessage.create_user_msg("User", text))
            self.signal_queue.put(PromptSignal(prompt=text))

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
        elif event.type == "stream_end":
            self._last_assistant_message = self._current_open_message
            self._current_open_message = None
        elif event.type == "stream_chunk":
            if event.chunk.choices[0].delta.content is not None:
                self._handle_message_content(event.chunk.choices[0].delta.content, None)
        elif event.type == "completion_response":
            if event.response.choices[0].message.content is not None:
                self._handle_message_content(
                    event.response.choices[0].message.content, None
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
        self, content: list[AssistantMessageChunk], fallback_author: str | None
    ):
        msg = self._ensure_open_message(fallback_author, overwrite=False)
        for content_chunk in content:
            if isinstance(content_chunk, TextChunk):
                msg.append_text(content_chunk.text)
            if isinstance(content_chunk, ThinkChunk):
                for think_chunk in content_chunk.thinking:
                    if isinstance(think_chunk, TextChunk):
                        msg.append_thinking(think_chunk.text)
