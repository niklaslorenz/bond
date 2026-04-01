from argparse import ArgumentParser, Namespace

from bond.behaviours.loop import LoopBehaviour
from bond.tui.app import BondTui


class TuiCommandHandler:
    app: BondTui
    beh: LoopBehaviour

    def __init__(self):
        pass

    def link(self, app: BondTui, beh: LoopBehaviour):
        self.app = app
        self.beh = beh

    def __call__(self, cmd: str):
        self.parser = ArgumentParser(exit_on_error=False)
        self._build_parser(self.parser)
        pass

    def quit(self, _: Namespace):
        self.app.quit()

    def load(self):
        pass

    def save(self, name: str | None):
        pass

    def new(self):
        pass

    def forget(self):
        pass

    def remember(self):
        pass

    def export(self):
        pass

    def crop(self):
        pass

    def to(self):
        pass

    def _build_parser(self, parser: ArgumentParser):
        subparsers = parser.add_subparsers()
