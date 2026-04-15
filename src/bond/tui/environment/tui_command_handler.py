from argparse import Namespace

from bond.behaviours.behaviour_event import ShowConversationSelectorEvent
from bond.environment.base_command_handler import BaseCommandHandler


class TuiCommandHandler(BaseCommandHandler):

    def load(self, args: Namespace) -> None:
        if args.name:
            super().load(args)
            return
        self.event_handler(
            ShowConversationSelectorEvent(conversations=self.list_conversations())
        )

    pass
