from argparse import Namespace
from multiprocessing import Queue
from pathlib import Path

from bond.behaviours.behaviour_event import BehaviourEvent, StopEvent
from bond.behaviours.loop import LoopBehaviour
from bond.std_command_handlerort DefaultCommandHandler


class TuiCommandHandler(DefaultCommandHandler):
    event_queue: Queue[BehaviourEvent]
    beh: LoopBehaviour

    def __init__(
        self,
        conversation_base_path: Path,
        last_conv_path: Path,
        available_personas: list[str],
        save_on_quit: bool = False,
    ):
        super().__init__(
            conversation_base_path,
            last_conv_path,
            available_personas,
            save_on_quit,
        )

    def link(self, event_queue: Queue[BehaviourEvent], beh: LoopBehaviour):
        self.event_queue = event_queue
        self.beh = beh

    def quit(self, args: Namespace):
        super().quit(args)
        self.event_queue.put(StopEvent())

    def load(self, args: Namespace):
        self.event_queue.put(BlockEvent())
        super().load(args)
        self.event_queue.put(
            SyncLogEvent(conversation=self.beh.conversation, message_count=None)
        )
        self.event_queue.put(ReleaseEvent())

    def save(self, args: Namespace):
        super().save(args)
        if args.name is not None:
            self.event_queue.put(NotifyEvent(message=f"Saved as '{args.name}'"))
        pass

    def clear_tool_calls(self, args: Namespace):
        super().clear_tool_calls(args)
        self.event_queue.put(
            SyncLogEvent(conversation=self.beh.conversation, message_count=None)
        )

    def new(self, args: Namespace):
        super().new(args)
        self.event_queue.put(ClearLogEvent())

    def forget(self, args: Namespace):
        super().forget(args)
        self.event_queue.put(StopEvent())

    def remember(self, args: Namespace):
        super().remember(args)
        self.event_queue.put(StopEvent())

    def export(self):
        self.event_queue.put(NotifyEvent(message="Not implemented"))

    def crop(self, args: Namespace):
        super().crop(args)
        self.event_queue.put(
            SyncLogEvent(conversation=self.beh.conversation, message_count=None)
        )

    def to(self, args: Namespace):
        super().to(args)
        self.event_queue.put(
            UpdatePersonaEvent(
                persona_name=self.beh.persona.name,
                provider_name=self.beh.persona.provider,
            )
        )

    def delete(self, args: Namespace):
        super().delete(args)
        self.event_queue.put(
            SyncLogEvent(conversation=self.beh.conversation, message_count=None)
        )
