"""Tests for persona-managed directories: ManagedDirectory, Persona.resolve_path,
Persona.managed_directory_for, and PersonaConfig validation."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from returns.result import Success

from bond.persona import (
    MANAGED_DIR_URI_PREFIX,
    ManagedDirectory,
    Persona,
    PersonaConfig,
)


def make_persona(managed_directories: list[ManagedDirectory]) -> Persona:
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
        managed_directories=managed_directories,
    )


class TestManagedDirectoryModel:
    def test_defaults_read_write(self):
        md = ManagedDirectory(name="sandbox", path="/tmp/x")
        assert md.read_only is False

    def test_read_only_flag(self):
        md = ManagedDirectory(name="archive", path="/tmp/x", read_only=True)
        assert md.read_only is True

    def test_invalid_names_rejected(self):
        for bad in ("", "a/b", ".", ".."):
            with pytest.raises(ValidationError):
                ManagedDirectory(name=bad, path="/tmp/x")

    def test_empty_path_rejected(self):
        with pytest.raises(ValidationError):
            ManagedDirectory(name="s", path="")


class TestPersonaConfigValidation:
    def test_managed_directories_default_empty(self):
        config = PersonaConfig(name="p", generation={})
        assert config.managed_directories == []

    def test_parses_managed_directories(self):
        config = PersonaConfig(
            name="p",
            generation={},
            managed_directories=[
                {"name": "sandbox", "path": "/tmp/sandbox"},
                {"name": "archive", "path": "/tmp/archive", "read_only": True},
            ],
        )
        assert [md.name for md in config.managed_directories] == [
            "sandbox",
            "archive",
        ]
        assert config.managed_directories[1].read_only is True

    def test_duplicate_names_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate managed directory"):
            PersonaConfig(
                name="p",
                generation={},
                managed_directories=[
                    {"name": "s", "path": "/tmp/a"},
                    {"name": "s", "path": "/tmp/b"},
                ],
            )

    def test_instantiate_passes_managed_directories(self, monkeypatch):
        provider = MagicMock()
        provider.generation.return_value = MagicMock()
        monkeypatch.setattr(
            "bond.persona._get_provider", lambda config, runtime: Success(provider)
        )
        config = PersonaConfig(
            name="p",
            generation={},
            managed_directories=[{"name": "s", "path": "/tmp/s"}],
        )
        persona = config.instantiate()
        assert [md.name for md in persona.managed_directories] == ["s"]


class TestResolvePath:
    def test_plain_paths_returned_as_is(self, tmp_path: Path):
        persona = make_persona([ManagedDirectory(name="s", path=str(tmp_path))])
        assert persona.resolve_path("rel/file.txt") == Path("rel/file.txt")
        assert persona.resolve_path(Path("rel/file.txt")) == Path("rel/file.txt")
        assert persona.resolve_path("/abs/file.txt") == Path("/abs/file.txt")

    def test_uri_maps_onto_managed_root(self, tmp_path: Path):
        persona = make_persona([ManagedDirectory(name="sandbox", path=str(tmp_path))])
        result = persona.resolve_path("bond://sandbox/foo/bar.txt")
        assert result == Path(os.path.normpath(tmp_path / "foo" / "bar.txt"))

    def test_bare_uri_addresses_root(self, tmp_path: Path):
        persona = make_persona([ManagedDirectory(name="sandbox", path=str(tmp_path))])
        assert persona.resolve_path("bond://sandbox") == Path(
            os.path.normpath(tmp_path)
        )

    def test_unknown_name_raises(self, tmp_path: Path):
        persona = make_persona([ManagedDirectory(name="sandbox", path=str(tmp_path))])
        with pytest.raises(ValueError, match="Unknown managed directory 'nope'"):
            persona.resolve_path("bond://nope/x")

    def test_empty_name_raises(self, tmp_path: Path):
        persona = make_persona([ManagedDirectory(name="sandbox", path=str(tmp_path))])
        with pytest.raises(ValueError, match="Unknown managed directory ''"):
            persona.resolve_path(MANAGED_DIR_URI_PREFIX)

    def test_escape_via_dotdot_rejected(self, tmp_path: Path):
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        persona = make_persona([ManagedDirectory(name="sandbox", path=str(sandbox))])
        with pytest.raises(ValueError, match="escapes managed directory 'sandbox'"):
            persona.resolve_path("bond://sandbox/../secret")
        with pytest.raises(ValueError, match="escapes managed directory 'sandbox'"):
            persona.resolve_path("bond://sandbox/../../etc/passwd")

    def test_tilde_in_managed_path_expanded(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        persona = make_persona([ManagedDirectory(name="s", path="~/sub")])
        result = persona.resolve_path("bond://s/x")
        assert result == Path(os.path.normpath(tmp_path / "sub" / "x"))

    def test_symlinked_root_not_resolved_but_usable(self, tmp_path: Path):
        real = tmp_path / "real"
        real.mkdir()
        (real / "foo.txt").write_text("hello", encoding="utf-8")
        link = tmp_path / "link"
        link.symlink_to(real)
        persona = make_persona([ManagedDirectory(name="s", path=str(link))])
        result = persona.resolve_path("bond://s/foo.txt")
        # lexical: still points through the symlink, not at the real dir
        assert result == Path(os.path.normpath(link / "foo.txt"))
        assert result != Path(os.path.normpath(real / "foo.txt"))
        # but the OS resolves the symlink on access
        assert result.read_text(encoding="utf-8") == "hello"


class TestManagedDirectoryFor:
    def test_path_inside_root_matches(self, tmp_path: Path):
        persona = make_persona([ManagedDirectory(name="s", path=str(tmp_path))])
        found = persona.managed_directory_for(tmp_path / "a" / "b.txt")
        assert found is not None and found.name == "s"

    def test_root_itself_matches(self, tmp_path: Path):
        persona = make_persona([ManagedDirectory(name="s", path=str(tmp_path))])
        assert persona.managed_directory_for(tmp_path) is not None

    def test_outside_path_returns_none(self, tmp_path: Path):
        persona = make_persona([ManagedDirectory(name="s", path=str(tmp_path))])
        assert persona.managed_directory_for(tmp_path.parent / "other") is None

    def test_relative_path_returns_none(self, tmp_path: Path):
        persona = make_persona([ManagedDirectory(name="s", path=str(tmp_path))])
        assert persona.managed_directory_for(Path("rel/x")) is None

    def test_read_only_flag_visible_through_lookup(self, tmp_path: Path):
        persona = make_persona(
            [ManagedDirectory(name="ro", path=str(tmp_path), read_only=True)]
        )
        found = persona.managed_directory_for(tmp_path / "f")
        assert found is not None and found.read_only is True
