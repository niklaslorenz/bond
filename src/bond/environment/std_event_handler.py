import sys

from bond.behaviours.behaviour_event import *
from bond.conversation.types import parse_chunks_content
from bond.environment.std_signal_receiver import StdSignalReceiver


class StdEventHandler:

    def __init__(
        self, receiver: StdSignalReceiver, show_thoughts: bool, show_tool_output: bool
    ):
        self._receiver = receiver
        self._show_thoughts = show_thoughts
        self._show_tool_output = show_tool_output
        self._has_open_thought_block = False

    def __call__(self, event: BehaviourEvent) -> None:
        handler = getattr(self, f"handle_{event.type}_event", self.handle_invalid_event)
        handler(event)

    def handle_error_event(self, event: ErrorEvent):
        print(
            f"Error {'(critical) ' if event.critical else ''} {type(event.error)}: {event.error}"
        )

    def handle_stop_event(self, _: StopEvent):
        self._receiver.stop()

    def handle_notify_event(self, event: NotifyEvent):
        self.notify(event.message)

    def handle_full_response_event(self, event: FullResponseEvent):
        print(f"\n{event.author}:")
        if (
            len(event.response.choices) == 0
            or event.response.choices[0].message.content is None
        ):
            return
        text, think = parse_chunks_content(event.response.choices[0].message.content)
        if think is not None and self._show_thoughts:
            print(f"[THINK]\n{think}\n[/THINK]")
        if text is not None:
            print(f"{text}\n")

    def handle_response_start_event(self, event: ResponseStartEvent):
        print(f"\n{event.author}:")
        self._has_open_thought_block = False

    def handle_response_end_event(self, _: ResponseEndEvent):
        if self._has_open_thought_block:
            print("\n[/THINK]")
        print("\n")
        self._has_open_thought_block = False

    def handle_waiting_for_input_event(self, _: WaitingForInputEvent):
        pass

    def handle_append_message_chunk_event(self, event: AppendMessageChunkEvent):
        if (
            len(event.chunk.choices) == 0
            or event.chunk.choices[0].delta.content is None
        ):
            return
        text, think = parse_chunks_content(event.chunk.choices[0].delta.content)
        if think is not None:
            if not self._has_open_thought_block:
                print("[THINK]")
                self._has_open_thought_block = True
            print(think, end="", flush=True)
        if text is not None:
            if self._has_open_thought_block:
                print("\n[/THINK]")
                self._has_open_thought_block = False
            print(text, end="", flush=True)

    def handle_request_confirmation_event(self, event: RequestConfirmationEvent):
        print(event.request)
        while True:
            result = input("[yes|no] > ")
            if result == "yes":
                event.result().set_result(True)
                return
            if result == "no":
                event.result().set_result(False)
                return

    def handle_cancel_request_confirmation_event(
        self, _: CancelRequestConfirmationEvent
    ):
        self(
            ErrorEvent(
                error=RuntimeError(
                    f"StdEventHandler cannot cancel confirmation requests"
                ),
                critical=False,
            )
        )

    def handle_call_tool_event(self, event: CallToolEvent):
        print(f"[Calling {event.call.function.name}]")

    def handle_tool_return_event(self, event: ToolReturnEvent):
        if self._show_tool_output:
            print(event.result)

    def handle_change_persona_event(self, _: ChangePersonaEvent):
        pass

    def handle_clear_chat_event(self, _: ClearChatEvent):
        print("\n\n\n")

    def handle_restore_conversation_event(self, _: RestoreConversationEvent):
        print("\n\n\n")

    def handle_invalid_event(self, event: BehaviourEvent):
        print(f"Invalid behaviour event: {event.type}", file=sys.stderr)

    def notify(self, msg: str):
        print(f"<{msg}>")
