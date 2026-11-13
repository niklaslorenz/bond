"""Tests for the ``tree`` file system tool."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bond.tools.file_system.tree import MAX_TREE_LINES, tree
from bond.tools.tool import ToolCallContext


def make_context(cwd: Path | None) -> ToolCallContext:
    return ToolCallContext(
        persona=None,
        stdout=None,
        stdin=None,
        is_interactive=True,
        cwd=cwd,
        logger=None,
        confirmation_prompt=lambda prompt: True,
        conversation=None,
    )


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")
    (tmp_path / "src" / "util").mkdir()
    (tmp_path / "src" / "util" / "helpers.py").write_text("x = 1\n")
    (tmp_path / "README.md").write_text("# readme\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("guide\n")
    return tmp_path


class TestTreeBasics:
    def test_lists_recursively_with_connectors(self, root: Path):
        out = tree(make_context(root), str(root))
        lines = out.splitlines()
        assert lines[0] == f"{root}/"
        # dirs first, then files, alphabetical within each group
        assert "├── docs/" in lines
        assert "├── src/" in lines
        assert "└── README.md" in lines
        # nested entries are indented under their parent
        assert "│   ├── util/" in lines
        assert "│   │   └── helpers.py" in lines
        assert "│   └── main.py" in lines
        assert "│   └── guide.md" in lines

    def test_max_depth_zero_shows_only_root(self, root: Path):
        out = tree(make_context(root), str(root), max_depth=0)
        assert out.splitlines() == [f"{root}/"]

    def test_max_depth_one_hides_grandchildren(self, root: Path):
        out = tree(make_context(root), str(root), max_depth=1)
        assert "├── src/" in out
        assert "main.py" not in out
        assert "helpers.py" not in out

    def test_max_depth_two_reaches_grandchildren(self, root: Path):
        out = tree(make_context(root), str(root), max_depth=2)
        assert "│   └── main.py" in out
        assert "helpers.py" not in out

    def test_negative_max_depth_is_an_error(self, root: Path):
        out = tree(make_context(root), str(root), max_depth=-1)
        assert "max_depth must be >= 0" in out

    def test_not_a_directory(self, root: Path):
        out = tree(make_context(root), str(root / "README.md"))
        assert "not a directory" in out

    def test_relative_path_resolved_against_cwd(self, root: Path):
        out = tree(make_context(root), "src")
        assert out.splitlines()[0] == f"{root / 'src'}/"
        assert "main.py" in out

    def test_disabled_filesystem(self, root: Path):
        out = tree(make_context(None), str(root))
        assert "disabled" in out

    def test_empty_directory(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        out = tree(make_context(tmp_path), str(empty))
        assert out.splitlines() == [f"{empty}/"]


class TestTreeSymlinks:
    def test_symlink_to_dir_shown_as_link_not_recursed(self, root: Path):
        link = root / "loop"
        os.symlink(root, link)
        out = tree(make_context(root), str(root), max_depth=10)
        assert f"└── loop -> {root}" in out.splitlines() or any(
            "loop -> " in line for line in out.splitlines()
        )
        # must terminate and not recurse into the link target
        assert out.count("loop -> ") == 1

    def test_symlink_to_file_shown_as_link(self, root: Path):
        link = root / "readme-link"
        os.symlink(root / "README.md", link)
        out = tree(make_context(root), str(root))
        assert any("readme-link -> " in line for line in out.splitlines())


class TestTreeLineCap:
    def test_truncates_at_max_lines_with_omission_notice(self, tmp_path: Path):
        for i in range(MAX_TREE_LINES + 50):
            (tmp_path / f"f{i:04d}.txt").write_text("x\n")
        out = tree(make_context(tmp_path), str(tmp_path), max_depth=1)
        lines = out.splitlines()
        # 1 root line + MAX-1 entries + 1 notice = MAX_TREE_LINES + 1 lines
        assert len(lines) == MAX_TREE_LINES + 1
        notice = lines[-1]
        assert notice.startswith("... (")
        assert "omitted" in notice
        # 51 lines omitted: 1 root + 250 entries = 251 total, 200 shown
        assert "51 more lines omitted" in notice

    def test_no_notice_when_under_cap(self, root: Path):
        out = tree(make_context(root), str(root))
        assert "omitted" not in out


class TestTreeAccess:
    def test_access_outside_cwd_denied_when_not_interactive(self, tmp_path: Path):
        project = tmp_path / "project"
        outside = tmp_path / "outside"
        project.mkdir()
        outside.mkdir()
        (outside / "a.txt").write_text("a\n")
        ctx = make_context(project)
        ctx.is_interactive = False
        out = tree(ctx, str(outside))
        assert "Permission denied" in out

    def test_access_outside_cwd_confirmed_interactively(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "a.txt").write_text("a\n")
        ctx = make_context(tmp_path / "project")  # cwd != outside's parent
        (tmp_path / "project").mkdir()
        out = tree(ctx, str(outside))
        assert "a.txt" in out

    def test_unknown_bond_uri_returns_error(self, tmp_path: Path):
        from bond.persona import ManagedDirectory, Persona, PersonaConfig

        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        persona = Persona(
            name="p",
            config=PersonaConfig(name="p", generation={}),
            generation=None,  # type: ignore[arg-type]
            summarization=None,
            thought_condensation=None,
            tts=None,
            memory=None,
            toolsets=[],
            runtime=MagicMock(),
            managed_directories=[ManagedDirectory(name="sandbox", path=str(sandbox))],
        )
        ctx = ToolCallContext(
            persona=persona,
            stdout=None,
            stdin=None,
            is_interactive=True,
            cwd=tmp_path,
            logger=None,
            confirmation_prompt=lambda prompt: True,
            conversation=None,
        )
        out = tree(ctx, "bond://nope/x")
        assert out.startswith("Error:")

    def test_bond_uri_works_with_managed_dir(self, tmp_path: Path):
        from bond.persona import ManagedDirectory, Persona, PersonaConfig

        sandbox = tmp_path / "sandbox"
        (sandbox / "sub").mkdir(parents=True)
        (sandbox / "sub" / "f.txt").write_text("x\n")
        persona = Persona(
            name="p",
            config=PersonaConfig(name="p", generation={}),
            generation=None,  # type: ignore[arg-type]
            summarization=None,
            thought_condensation=None,
            tts=None,
            memory=None,
            toolsets=[],
            runtime=MagicMock(),
            managed_directories=[ManagedDirectory(name="sandbox", path=str(sandbox))],
        )
        ctx = ToolCallContext(
            persona=persona,
            stdout=None,
            stdin=None,
            is_interactive=False,
            cwd=None,  # managed dirs work even with cwd disabled
            logger=None,
            confirmation_prompt=None,
            conversation=None,
        )
        out = tree(ctx, "bond://sandbox")
        assert "sub/" in out
        assert "f.txt" in out
