from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from bond.behaviours.types import LoopStatus


class StatusBar(Static):
    persona = reactive("<unknown>")
    status = reactive("Idle")
    context_length: reactive[int] = reactive(0)
    cache_hit_rate: reactive[tuple[int, int] | None] = reactive(None)
    cached_prefix_portion: reactive[float | None] = reactive(None)

    def __init__(
        self,
        persona: str = "<unknown>",
        status: str = "<unknown>",
        context_length: int = 0,
    ):
        super().__init__(id="status-bar")
        self.persona = persona
        self.status = status
        self.context_length = context_length

    def render(self) -> Text:
        return Text.assemble(
            ("Persona: ", "bold"),
            f"{self.persona}  ",
            ("Status: ", "bold"),
            f"{self.status}  ",
            ("Context: ", "bold"),
            f"{self.context_length}  ",
            ("Cached Prefix: ", "bold"),
            (
                f"{int(self.cached_prefix_portion * 100)}%  "
                if self.cached_prefix_portion is not None
                else "?  "
            ),
            ("Hit Rate: ", "bold"),
            (
                f"{int(self.cache_hit_rate[0] / self.cache_hit_rate[1] * 100)}%"
                if self.cache_hit_rate is not None
                else "?"
            ),
        )

    # Control

    def set_status(self, status: LoopStatus):
        self.status = status

    def set_usage(self, usage: int):
        self.context_length = usage

    def set_cached_prefix_portion(self, cached_prefix_portion: float | None):
        self.cached_prefix_portion = cached_prefix_portion

    def set_persona(self, persona_name: str):
        self.persona = persona_name

    def set_cache_hit_rate(self, cache_hit_rate: tuple[int, int] | None):
        self.cache_hit_rate = cache_hit_rate

    def add_cache_hit(self):
        if self.cache_hit_rate is None:
            self.cache_hit_rate = (1, 1)
        else:
            self.cache_hit_rate = (
                self.cache_hit_rate[0] + 1,
                self.cache_hit_rate[1] + 1,
            )

    def add_cache_miss(self):
        if self.cache_hit_rate is None:
            self.cache_hit_rate = (0, 1)
        else:
            self.cache_hit_rate = (self.cache_hit_rate[0], self.cache_hit_rate[1] + 1)
