import itertools
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel


class WorkingSetItemBase(ABC):
    @abstractmethod
    def render(self) -> str: ...


class TextItem(WorkingSetItemBase, BaseModel):
    type: Literal["text"] = "text"
    text: str

    def render(self) -> str:
        return self.text


class FileReferenceItem(WorkingSetItemBase, BaseModel):
    type: Literal["file"] = "file"
    path: str
    start_line: int | None
    end_line: int | None

    def model_post_init(self, context: Any, /) -> None:
        if self.start_line is not None and self.start_line < 0:
            raise ValueError("start_line must be greater than or equal 0")
        if self.end_line is not None and self.end_line < 0:
            raise ValueError("end_line must be greater than or equal 0")

    def render(self) -> str:
        path = Path(self.path).expanduser().absolute()
        if not path.exists():
            return f"<file '{path.as_posix()}' does not exist.>"

        if not path.is_file():
            return f"'{path.as_posix()}' is not a file.>"
        lines = path.read_text(encoding="utf-8").splitlines()
        # TODO: render file content with optional line numbering like the read_file tool does
        return (
            f"Contents of '{path.as_posix()}(lines {(self.start_line or 0) + 1} to {self.end_line or '<eof>'})':\n"
            + "\n".join(lines[self.start_line : self.end_line])
        )


MAX_DIR_ENTRIES = 64


class DirectoryReferenceItem(WorkingSetItemBase, BaseModel):
    type: Literal["directory"] = "directory"
    path: str
    pattern: str
    recursive: bool
    case_sensitive: bool

    def render(self) -> str:
        path = Path(self.path).expanduser().absolute()
        if not path.exists():
            return f"<directory '{path.as_posix()}' does not exist.>"

        if not path.is_dir():
            return f"<'{path.as_posix()}' is not a directory.>"
        results = (path.rglob if self.recursive else path.glob)(
            self.pattern, case_sensitive=self.case_sensitive
        )
        lines = [res.as_posix() for res in itertools.islice(results, MAX_DIR_ENTRIES)]
        return f"Contents of '{path.as_posix()}':\n" + "\n".join(lines)


WorkingSetItem = TextItem | FileReferenceItem | DirectoryReferenceItem
