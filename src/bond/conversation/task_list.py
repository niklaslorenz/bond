from typing import Iterator, overload

from pydantic import BaseModel, Field


class TaskListItem(BaseModel):
    _index: int
    _task: str
    _complete: bool

    @property
    def index(self) -> int:
        return self._index

    @property
    def description(self) -> str:
        return self._task

    @property
    def is_complete(self) -> int:
        return self._complete

    def render(self) -> str:
        return f"{self.index}. [{'x' if self._complete else ' '}] {self._task}"


class TaskList(BaseModel):
    _content: list[TaskListItem] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self._content)

    @overload
    def __getitem__(self, index: int) -> TaskListItem: ...

    @overload
    def __getitem__(self, index: slice) -> list[TaskListItem]: ...

    def __getitem__(self, index: int | slice) -> TaskListItem | list[TaskListItem]:
        return self._content[index]

    def __iter__(self) -> Iterator[TaskListItem]:
        return iter(self._content)

    def complete_item(self, index: int) -> TaskListItem:
        item = self._content[index]
        item._complete = True
        return item

    def render(self) -> str:
        return "\n".join([item.render() for item in self._content])

    def clear_complete_items(self) -> None:
        self._content = [item for item in self._content if not item.is_complete]
        self._recompute_index()

    def add_item(self, item: str) -> TaskListItem:
        new_item = TaskListItem(_index=len(self), _task=item, _complete=False)
        self._content.append(new_item)
        return new_item

    def remove_item(self, index: int) -> TaskListItem:
        item = self._content[index]
        self._content.remove(item)
        self._recompute_index()
        return item

    def _recompute_index(self):
        for i, item in enumerate(self._content):
            item._index = i
