import textwrap
from typing import Iterator, overload

from pydantic import BaseModel, Field

from bond.conversation.working_set_item import WorkingSetItem


class WorkingSet(BaseModel):
    items: list[WorkingSetItem] = Field(default_factory=list)
    displayed: str | None = None

    def __len__(self) -> int:
        return len(self.items)

    @overload
    def __getitem__(self, index: int) -> WorkingSetItem: ...

    @overload
    def __getitem__(self, index: slice) -> list[WorkingSetItem]: ...

    def __getitem__(self, index: int | slice) -> WorkingSetItem | list[WorkingSetItem]:
        return self.items[index]

    def __iter__(self) -> Iterator[WorkingSetItem]:
        return iter(self.items)

    def render(self) -> str:
        if self.displayed is None:
            return self.update()
        return self.displayed

    def update(self) -> str:
        self.displayed = "".join(textwrap.dedent(f"""
            <item index={idx}>
            {item.render()}
            </item>
            """) for idx, item in enumerate(self.items))
        return self.displayed

    def add_item(self, item: WorkingSetItem) -> WorkingSetItem:
        self.items.append(item)
        return item

    def remove_item(self, index: int) -> WorkingSetItem:
        return self.items.pop(index)

    def clear(self) -> int:
        count = len(self.items)
        self.items = []
        return count
