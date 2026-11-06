"""Tests for the `bond` CLI subcommands in bond.cli.bond."""

import sys
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from bond.cli.bond import list_skills, main
from bond.registry import NamedEntryRegistry
from bond.runtime import BondRuntime, DynamicRuntimeEnvironment
from bond.skill import Skill


@pytest.fixture
def skill_config_dir(tmp_path: Path):
    """Point the runtime singleton at a fresh dynamic environment in tmp_path.

    `initialize_dynamic` would overwrite `_environment` with the real
    ~/.config/bond, so it is patched out; the environment is installed
    directly instead. The skill cache registry is swapped for a fresh one so
    registrations during a test do not leak into other tests.
    """
    config_dir = tmp_path / "config"
    (config_dir / "skills").mkdir(parents=True)
    runtime = BondRuntime.get_instance()
    old_env = runtime._environment
    old_loaded_skills = runtime._loaded_skills
    runtime._environment = DynamicRuntimeEnvironment(config_dir, tmp_path / "data")
    runtime._loaded_skills = NamedEntryRegistry[Skill]()
    with patch.object(runtime, "initialize_dynamic", return_value=runtime._environment):
        yield config_dir
    runtime._environment = old_env
    runtime._loaded_skills = old_loaded_skills


def _write_skill(
    config_dir: Path, name: str, skill_md: str | None = "---\n---\nbody\n"
):
    skill_dir = config_dir / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    if skill_md is not None:
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")


class TestListSkillsCommand:
    def test_no_skills_found(self, skill_config_dir, capsys):
        list_skills(Namespace())
        assert capsys.readouterr().out == "No skills found\n"

    def test_lists_skills_with_descriptions(self, skill_config_dir, capsys):
        _write_skill(
            skill_config_dir,
            "pdf",
            "---\ndescription: PDF tools\n---\nUse pdf tools.\n",
        )
        _write_skill(skill_config_dir, "git", "---\n---\nNo description.\n")
        list_skills(Namespace())
        out = capsys.readouterr().out
        assert out.startswith("Skills:\n")
        assert "  git\n" in out  # no description -> bare name
        assert "  pdf: PDF tools\n" in out

    def test_skills_sorted_and_dir_without_skill_md_ignored(
        self, skill_config_dir, capsys
    ):
        _write_skill(skill_config_dir, "zeta", None)  # dir without SKILL.md
        _write_skill(skill_config_dir, "beta", "---\ndescription: b\n---\n")
        _write_skill(skill_config_dir, "alpha", "---\ndescription: a\n---\n")
        list_skills(Namespace())
        out = capsys.readouterr().out
        assert out == "Skills:\n  alpha: a\n  beta: b\n"

    def test_main_dispatches_skills_subcommand(self, skill_config_dir, capsys):
        _write_skill(skill_config_dir, "pdf", "---\ndescription: PDF tools\n---\n")
        with patch.object(sys, "argv", ["bond", "skills"]):
            assert main() == 0
        assert "  pdf: PDF tools\n" in capsys.readouterr().out
