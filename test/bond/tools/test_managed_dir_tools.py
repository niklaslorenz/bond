"""Tests for ``bond://`` managed-directory URIs in the file system tools
and for ``ToolCallContext.resolve_path``."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bond.persona import ManagedDirectory, Persona, PersonaConfig
from bond.tools.file_system.apply_patch import apply_patch
from bond.tools.file_system.create_file import create_file
from bond.tools.file_system.grep import grep
from bond.tools.file_system.list_directory import list_directory
from bond.tools.file_system.read_file import read_file
from bond.tools.file_system.remove_file import remove_file
from bond.tools.file_system.search import search_file
from bond.tools.tool import ToolCallContext


def make_persona(sandbox: Path, archive: Path | None = None) -> Persona:
    dirs = [ManagedDirectory(name="sandbox", path=str(sandbox))]
    if archive is not None:
        dirs.append(
            ManagedDirectory(name="archive", path=str(archive), read_only=True)
        )
    return Persona(
        name="p",
        config=PersonaConfig(name="p", generation={}),
        generation=None,  # type: ignore[arg-type]
        summarization=None,
        thought_condensation=None,
        tts=None,
        memory=None,
        toolsets=[],
        runtime=MagicMock(),
        managed_directories=dirs,
    )


def make_context(persona: Persona | None, cwd: Path | None) -> ToolCallContext:
    return ToolCallContext(
        persona=persona,
        stdout=None,
        stdin=None,
        is_interactive=True,
        cwd=cwd,
        logger=None,
        confirmation_prompt=lambda prompt: True,
        conversation=None,
    )


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    sandbox = tmp_path / "sandbox"
    archive = tmp_path / "archive"
    sandbox.mkdir()
    archive.mkdir()
    return sandbox, archive


@pytest.fixture
def persona(dirs: tuple[Path, Path]) -> Persona:
    sandbox, archive = dirs
    return make_persona(sandbox, archive)


class TestResolvePathOnContext:
    def test_bond_uri_maps_to_managed_root(
        self, tmp_path: Path, persona: Persona
    ):
        sandbox, _ = make_dirs(tmp_path)
        ctx = make_context(persona, tmp_path)
        assert ctx.resolve_path("bond://sandbox/a/b.txt") == sandbox / "a" / "b.txt"

    def test_bond_uri_root(self, tmp_path: Path, persona: Persona):
        sandbox, _ = make_dirs(tmp_path)
        ctx = make_context(persona, tmp_path)
        assert ctx.resolve_path("bond://sandbox") == sandbox

    def test_absolute_passthrough(self, tmp_path: Path, persona: Persona):
        ctx = make_context(persona, tmp_path)
        assert ctx.resolve_path("/etc/hosts") == Path("/etc/hosts")

    def test_relative_resolved_against_cwd(self, tmp_path: Path, persona: Persona):
        ctx = make_context(persona, tmp_path)
        assert ctx.resolve_path("x/y.txt") == tmp_path / "x" / "y.txt"

    def test_relative_with_cwd_none_returns_none(
        self, tmp_path: Path, persona: Persona
    ):
        ctx = make_context(persona, None)
        assert ctx.resolve_path("x.txt") is None

    def test_bond_uri_works_with_cwd_none(self, tmp_path: Path, persona: Persona):
        sandbox, _ = make_dirs(tmp_path)
        ctx = make_context(persona, None)
        assert ctx.resolve_path("bond://sandbox/x") == sandbox / "x"

    def test_unknown_name_raises(self, tmp_path: Path, persona: Persona):
        ctx = make_context(persona, tmp_path)
        with pytest.raises(ValueError, match="Unknown managed directory 'nope'"):
            ctx.resolve_path("bond://nope/x")

    def test_escape_raises(self, tmp_path: Path, persona: Persona):
        ctx = make_context(persona, tmp_path)
        with pytest.raises(ValueError, match="escapes managed directory 'sandbox'"):
            ctx.resolve_path("bond://sandbox/../outside")

    def test_no_persona_plain_resolution(self, tmp_path: Path):
        ctx = make_context(None, tmp_path)
        assert ctx.resolve_path("x.txt") == tmp_path / "x.txt"
        assert ctx.resolve_path("/abs") == Path("/abs")
        assert make_context(None, None).resolve_path("x.txt") is None


def make_dirs(tmp_path: Path) -> tuple[Path, Path]:
    sandbox = tmp_path / "sandbox"
    archive = tmp_path / "archive"
    sandbox.mkdir(exist_ok=True)
    archive.mkdir(exist_ok=True)
    return sandbox, archive


class TestReadViaBondUri:
    def test_read_file_via_uri_with_cwd_none(
        self, tmp_path: Path, persona: Persona
    ):
        sandbox, _ = make_dirs(tmp_path)
        (sandbox / "note.txt").write_text("hello managed\n", encoding="utf-8")
        ctx = make_context(persona, None)  # cwd disabled
        result = read_file(ctx, "bond://sandbox/note.txt")
        assert "hello managed" in result

    def test_list_directory_via_uri_root(self, tmp_path: Path, persona: Persona):
        sandbox, _ = make_dirs(tmp_path)
        (sandbox / "a.txt").write_text("a", encoding="utf-8")
        ctx = make_context(persona, None)
        result = list_directory(ctx, "bond://sandbox")
        assert "a.txt" in result

    def test_search_file_via_uri(self, tmp_path: Path, persona: Persona):
        sandbox, _ = make_dirs(tmp_path)
        (sandbox / "note.txt").write_text("needle here\n", encoding="utf-8")
        ctx = make_context(persona, None)
        result = search_file(ctx, "bond://sandbox/note.txt", "needle")
        assert "needle here" in result

    def test_grep_via_uri(self, tmp_path: Path, persona: Persona):
        sandbox, _ = make_dirs(tmp_path)
        (sandbox / "note.txt").write_text("hello grep\n", encoding="utf-8")
        ctx = make_context(persona, None)
        result = grep(ctx, "hello", "bond://sandbox")
        assert "hello grep" in result

    def test_unknown_name_error_string(self, tmp_path: Path, persona: Persona):
        ctx = make_context(persona, None)
        result = read_file(ctx, "bond://nope/x.txt")
        assert result.startswith("Error:")
        assert "Unknown managed directory 'nope'" in result

    def test_escape_error_string(self, tmp_path: Path, persona: Persona):
        ctx = make_context(persona, None)
        result = read_file(ctx, "bond://sandbox/../outside.txt")
        assert result.startswith("Error:")
        assert "escapes managed directory 'sandbox'" in result


class TestWritePermissions:
    def test_create_file_in_read_write_managed_dir_with_cwd_none(
        self, tmp_path: Path, persona: Persona
    ):
        sandbox, _ = make_dirs(tmp_path)
        ctx = make_context(persona, None)
        result = create_file(ctx, "bond://sandbox/new.txt", "hi")
        assert "Created file at" in result
        assert (sandbox / "new.txt").read_text(encoding="utf-8") == "hi"

    def test_create_file_in_read_only_dir_denied(
        self, tmp_path: Path, persona: Persona
    ):
        _, archive = make_dirs(tmp_path)
        ctx = make_context(persona, None)
        result = create_file(ctx, "bond://archive/new.txt", "hi")
        assert "Permission denied" in result
        assert "read-only" in result
        assert not (archive / "new.txt").exists()

    def test_remove_file_in_read_only_dir_denied(
        self, tmp_path: Path, persona: Persona
    ):
        _, archive = make_dirs(tmp_path)
        target = archive / "old.txt"
        target.write_text("old", encoding="utf-8")
        ctx = make_context(persona, None)
        result = remove_file(ctx, "bond://archive/old.txt")
        assert "Permission denied" in result
        assert "read-only" in result
        assert target.exists()

    def test_bond_dir_inside_managed_dir_still_write_denied(
        self, tmp_path: Path, persona: Persona
    ):
        sandbox, _ = make_dirs(tmp_path)
        ctx = make_context(persona, None)
        result = create_file(ctx, "bond://sandbox/.bond/x", "hi")
        assert "Permission denied" in result
        assert "`.bond`" in result
        assert not (sandbox / ".bond").exists()

    def test_apply_patch_block_via_uri(self, tmp_path: Path, persona: Persona):
        sandbox, _ = make_dirs(tmp_path)
        target = sandbox / "keep.md"
        target.write_text("keep\n", encoding="utf-8")
        ctx = make_context(persona, None)
        patch = (
            "bond://sandbox/keep.md\n"
            "<<<<<<< SEARCH\n"
            "keep\n"
            "=======\n"
            "changed\n"
            ">>>>>>> REPLACE"
        )
        result = apply_patch(ctx, patch)
        assert "success" in result
        assert target.read_text(encoding="utf-8") == "changed\n"

    def test_apply_patch_block_in_read_only_dir_denied(
        self, tmp_path: Path, persona: Persona
    ):
        _, archive = make_dirs(tmp_path)
        target = archive / "keep.md"
        target.write_text("keep\n", encoding="utf-8")
        ctx = make_context(persona, None)
        patch = (
            "bond://archive/keep.md\n"
            "<<<<<<< SEARCH\n"
            "keep\n"
            "=======\n"
            "changed\n"
            ">>>>>>> REPLACE"
        )
        result = apply_patch(ctx, patch)
        assert "Block 0: failed" in result
        assert "read-only" in result
        assert target.read_text(encoding="utf-8") == "keep\n"
