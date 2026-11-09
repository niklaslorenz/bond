"""Tests for bond.local discovery and BondRuntime's local .bond integration."""

from pathlib import Path

import pytest

from bond.local import LOCAL_DIR_NAME, find_local_bond_dir
from bond.registry import NamedEntryRegistry
from bond.runtime import BondRuntime, DynamicRuntimeEnvironment
from bond.skill import Skill


@pytest.fixture
def runtime_env(tmp_path: Path):
    """Install a fresh dynamic environment in tmp_path on the runtime singleton
    and restore the previous state afterwards.

    ``initialize_dynamic`` re-registers the builtin toolsets/provider types
    without clearing the registries first, so tests that call it must clear
    those two registries beforehand (see ``_reinit``).
    """
    runtime = BondRuntime.get_instance()
    saved = {
        "_environment": runtime._environment,
        "_disable_local_config": runtime._disable_local_config,
        "_local_skill_cache": runtime._local_skill_cache,
        "_loaded_skills": runtime._loaded_skills,
        "_toolset_registry": runtime._toolset_registry,
        "_provider_type_registry": runtime._provider_type_registry,
    }
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    (config_dir / "skills").mkdir(parents=True)
    runtime._environment = DynamicRuntimeEnvironment(config_dir, data_dir)
    runtime._disable_local_config = False
    runtime._local_skill_cache = {}
    runtime._loaded_skills = NamedEntryRegistry[Skill]()
    yield runtime, config_dir, data_dir
    for attr, value in saved.items():
        setattr(runtime, attr, value)


def _reinit(runtime: BondRuntime, config_dir: Path, data_dir: Path, **kwargs):
    """Re-run initialize_dynamic on the singleton without duplicate-registration
    errors (the builtin registries are cleared first, as initialize_dynamic
    does not clear them itself)."""
    runtime._toolset_registry.clear()
    runtime._provider_type_registry.clear()
    return runtime.initialize_dynamic(
        config_dir=config_dir, data_dir=data_dir, enable_plugins=False, **kwargs
    )


def _write_skill(skills_dir: Path, name: str, instructions: str):
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill\n---\n{instructions}\n",
        encoding="utf-8",
    )


class TestFindLocalBondDir:
    def test_finds_in_start_dir(self, tmp_path: Path):
        (tmp_path / LOCAL_DIR_NAME).mkdir()
        assert find_local_bond_dir(tmp_path) == tmp_path / LOCAL_DIR_NAME

    def test_finds_in_parent(self, tmp_path: Path):
        (tmp_path / LOCAL_DIR_NAME).mkdir()
        sub = tmp_path / "sub"
        sub.mkdir()
        assert find_local_bond_dir(sub) == tmp_path / LOCAL_DIR_NAME

    def test_closest_wins(self, tmp_path: Path):
        outer = tmp_path / "outer"
        inner = outer / "inner"
        deep = outer / "deep"
        inner.mkdir(parents=True)
        deep.mkdir()
        (outer / LOCAL_DIR_NAME).mkdir()
        (inner / LOCAL_DIR_NAME).mkdir()
        assert find_local_bond_dir(inner) == inner / LOCAL_DIR_NAME
        assert find_local_bond_dir(deep) == outer / LOCAL_DIR_NAME

    def test_none_when_absent(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert find_local_bond_dir(empty) is None

    def test_file_start_uses_parent(self, tmp_path: Path):
        (tmp_path / LOCAL_DIR_NAME).mkdir()
        file = tmp_path / "file"
        file.touch()
        assert find_local_bond_dir(file) == tmp_path / LOCAL_DIR_NAME


class TestRuntimeLocalBondDir:
    def test_no_bond_dir(self, runtime_env, tmp_path: Path, monkeypatch):
        runtime, config_dir, data_dir = runtime_env
        # Run from a directory with no .bond in any ancestor (the repo itself
        # now has one, since .bond/scripts/run-tests.sh exists).
        monkeypatch.chdir(tmp_path)
        assert runtime.get_local_bond_dir() is None
        assert runtime.get_local_skills_path() is None
        assert runtime.get_local_scripts_path() is None
        assert runtime.get_local_conversations_path() is None

    def test_paths_point_into_bond_dir(self, runtime_env, monkeypatch):
        runtime, config_dir, data_dir = runtime_env
        monkeypatch.chdir(config_dir)
        bond_dir = config_dir / LOCAL_DIR_NAME
        bond_dir.mkdir()
        assert runtime.get_local_bond_dir() == bond_dir
        assert runtime.get_local_skills_path() == bond_dir / "skills"
        assert runtime.get_local_scripts_path() == bond_dir / "scripts"
        assert runtime.get_local_conversations_path() == bond_dir / "conversations"

    def test_disable_local_config_hides_bond_dir(self, runtime_env, monkeypatch):
        runtime, config_dir, data_dir = runtime_env
        monkeypatch.chdir(config_dir)
        bond_dir = config_dir / LOCAL_DIR_NAME
        bond_dir.mkdir()
        assert runtime.get_local_bond_dir() == bond_dir

        _reinit(runtime, config_dir, data_dir, disable_local_config=True)
        assert runtime.get_local_bond_dir() is None
        assert runtime.get_local_skills_path() is None


class TestLocalSkillPrecedence:
    def test_local_skill_shadows_global(self, runtime_env, monkeypatch):
        runtime, config_dir, data_dir = runtime_env
        bond_dir = config_dir / LOCAL_DIR_NAME
        bond_dir.mkdir()
        _write_skill(config_dir / "skills", "ghost", "global instructions")
        _write_skill(bond_dir / "skills", "ghost", "local instructions")

        monkeypatch.chdir(config_dir)
        assert "ghost" in runtime.list_skills()
        skill = runtime.get_skill("ghost").unwrap()
        assert "local instructions" in skill.instructions

    def test_disable_local_config_returns_global(self, runtime_env, monkeypatch):
        runtime, config_dir, data_dir = runtime_env
        bond_dir = config_dir / LOCAL_DIR_NAME
        bond_dir.mkdir()
        _write_skill(config_dir / "skills", "ghost", "global instructions")
        _write_skill(bond_dir / "skills", "ghost", "local instructions")

        monkeypatch.chdir(config_dir)
        _reinit(runtime, config_dir, data_dir, disable_local_config=True)
        skill = runtime.get_skill("ghost").unwrap()
        assert "global instructions" in skill.instructions

    def test_local_only_skill_not_listed_when_disabled(
        self, runtime_env, monkeypatch
    ):
        runtime, config_dir, data_dir = runtime_env
        bond_dir = config_dir / LOCAL_DIR_NAME
        bond_dir.mkdir()
        _write_skill(bond_dir / "skills", "local-only", "local only")

        monkeypatch.chdir(config_dir)
        assert "local-only" in runtime.list_skills()

        _reinit(runtime, config_dir, data_dir, disable_local_config=True)
        assert "local-only" not in runtime.list_skills()


class TestListLocalSkills:
    def test_lists_local_skill_dirs_with_skill_md(self, runtime_env, monkeypatch):
        runtime, config_dir, data_dir = runtime_env
        bond_dir = config_dir / LOCAL_DIR_NAME
        _write_skill(bond_dir / "skills", "beta", "b")
        _write_skill(bond_dir / "skills", "alpha", "a")
        (bond_dir / "skills" / "no-md").mkdir(parents=True)  # no SKILL.md -> skip
        _write_skill(config_dir / "skills", "global-one", "g")  # not local

        monkeypatch.chdir(config_dir)
        assert runtime.list_local_skills() == ["alpha", "beta"]

    def test_empty_when_no_bond_dir(self, runtime_env, tmp_path, monkeypatch):
        runtime, config_dir, data_dir = runtime_env
        monkeypatch.chdir(tmp_path)
        assert runtime.list_local_skills() == []

    def test_empty_when_disabled(self, runtime_env, monkeypatch):
        runtime, config_dir, data_dir = runtime_env
        bond_dir = config_dir / LOCAL_DIR_NAME
        _write_skill(bond_dir / "skills", "local-only", "x")

        monkeypatch.chdir(config_dir)
        assert runtime.list_local_skills() == ["local-only"]

        _reinit(runtime, config_dir, data_dir, disable_local_config=True)
        assert runtime.list_local_skills() == []


class TestPathKeyedSkillCache:
    def test_same_name_different_projects(self, runtime_env, tmp_path: Path, monkeypatch):
        runtime, _, _ = runtime_env
        old_cache = runtime._local_skill_cache
        old_loaded_skills = runtime._loaded_skills
        runtime._local_skill_cache = {}
        runtime._loaded_skills = NamedEntryRegistry[Skill]()
        try:
            projects = []
            for name in ("proj_a", "proj_b"):
                project = tmp_path / name
                project.mkdir()
                bond_skills = project / LOCAL_DIR_NAME / "skills"
                bond_skills.mkdir(parents=True)
                _write_skill(bond_skills, "shared", f"instructions of {name}")
                projects.append(project)

            monkeypatch.chdir(projects[0])
            assert "proj_a" in runtime.get_skill("shared").unwrap().instructions

            monkeypatch.chdir(projects[1])
            assert "proj_b" in runtime.get_skill("shared").unwrap().instructions

            # going back must return the cached proj_a instance
            monkeypatch.chdir(projects[0])
            assert "proj_a" in runtime.get_skill("shared").unwrap().instructions
        finally:
            runtime._local_skill_cache = old_cache
            runtime._loaded_skills = old_loaded_skills
