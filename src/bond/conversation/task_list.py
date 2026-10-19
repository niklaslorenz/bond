from typing import Iterator, overload

from pydantic import BaseModel, Field


class TaskListItem(BaseModel):
    index: int
    description: str
    is_complete: bool

    def render(self) -> str:
        return f"{self.index}. [{'x' if self.is_complete else ' '}] {self.description}"


class TaskList(BaseModel):
    content: list[TaskListItem] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.content)

    @overload
    def __getitem__(self, index: int) -> TaskListItem: ...

    @overload
    def __getitem__(self, index: slice) -> list[TaskListItem]: ...

    def __getitem__(self, index: int | slice) -> TaskListItem | list[TaskListItem]:
        return self.content[index]

    def __iter__(self) -> Iterator[TaskListItem]:
        return iter(self.content)

    def complete_item(self, index: int) -> TaskListItem:
        item = self.content[index]
        item.is_complete = True
        return item

    def render(self) -> str:
        return "\n".join([item.render() for item in self.content])

    def clear_complete_items(self) -> None:
        self.content = [item for item in self.content if not item.is_complete]
        self._recompute_index()

    def add_item(self, item: str) -> TaskListItem:
        new_item = TaskListItem(index=len(self), description=item, is_complete=False)
        self.content.append(new_item)
        return new_item

    def remove_item(self, index: int) -> TaskListItem:
        item = self.content[index]
        self.content.remove(item)
        self._recompute_index()
        return item

    def _recompute_index(self):
        for i, item in enumerate(self.content):
            item.index = i
