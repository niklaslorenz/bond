"""Tests for bond.skill (parser, helper) and the skill support in bond.runtime."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bond.config import BondConfig
from bond.conversation.conversation import Conversation
from bond.persona import Persona, PersonaConfig
from bond.runtime import (
    BondRuntime,
    DynamicRuntimeEnvironment,
    StaticRuntimeEnvironment,
)
from bond.skill import (
    Skill,
    effective_available_skills,
    parse_skill_md,
    prune_active_skills,
)

# ---------------------------------------------------------------------------
# parse_skill_md
# ---------------------------------------------------------------------------


class TestParseSkillMd:
    def test_full_frontmatter(self):
        text = (
            "---\n"
            "name: pdf-tools\n"
            "description: Tools for extracting and analyzing PDFs.\n"
            "---\n"
            "# Instructions\n"
            "Use these tools when the user mentions PDFs.\n"
        )
        skill = parse_skill_md(text, fallback_name="pdf")
        assert skill.name == "pdf-tools"
        assert skill.description == "Tools for extracting and analyzing PDFs."
        assert skill.instructions == (
            "# Instructions\nUse these tools when the user mentions PDFs."
        )

    def test_frontmatter_name_wins_over_fallback(self):
        text = "---\nname: other-name\ndescription: d\n---\nbody\n"
        skill = parse_skill_md(text, fallback_name="dir-name")
        assert skill.name == "other-name"

    def test_no_frontmatter_uses_fallback_name(self):
        skill = parse_skill_md("Just instructions, no frontmatter.", "my-skill")
        assert skill.name == "my-skill"
        assert skill.description == ""
        assert skill.instructions == "Just instructions, no frontmatter."

    def test_frontmatter_without_name_uses_fallback(self):
        text = "---\ndescription: only a description\n---\nbody\n"
        skill = parse_skill_md(text, fallback_name="dir-name")
        assert skill.name == "dir-name"
        assert skill.description == "only a description"
        assert skill.instructions == "body"

    def test_frontmatter_without_description_defaults_to_empty(self):
        text = "---\nname: x\n---\nbody\n"
        skill = parse_skill_md(text, fallback_name="fallback")
        assert skill.name == "x"
        assert skill.description == ""

    def test_unknown_frontmatter_keys_are_ignored(self):
        text = "---\nname: x\nauthor: someone\nversion: 1.0\n---\nbody\n"
        skill = parse_skill_md(text, fallback_name="fallback")
        assert skill.name == "x"
        assert skill.instructions == "body"

    def test_quoted_values_are_unquoted(self):
        text = '---\nname: "quoted"\ndescription: \'single quoted\'\n---\nbody\n'
        skill = parse_skill_md(text, fallback_name="fallback")
        assert skill.name == "quoted"
        assert skill.description == "single quoted"

    def test_crlf_line_endings(self):
        text = "---\r\nname: crlf\r\ndescription: windows\r\n---\r\nbody\r\n"
        skill = parse_skill_md(text, fallback_name="fallback")
        assert skill.name == "crlf"
        assert skill.description == "windows"
        assert skill.instructions == "body"

    def test_instructions_stripped_of_surrounding_newlines(self):
        text = "---\nname: x\n---\n\n\nbody\n\n\n"
        skill = parse_skill_md(text, fallback_name="fallback")
        assert skill.instructions == "body"

    def test_empty_body(self):
        text = "---\nname: x\ndescription: d\n---\n"
        skill = parse_skill_md(text, fallback_name="fallback")
        assert skill.instructions == ""

    def test_dashes_in_body_not_treated_as_frontmatter(self):
        text = "---\nname: x\n---\nsome text\n---\nmore text\n"
        skill = parse_skill_md(text, fallback_name="fallback")
        assert skill.instructions == "some text\n---\nmore text"


# ---------------------------------------------------------------------------
# DynamicRuntimeEnvironment
# ---------------------------------------------------------------------------


def _make_skill_dir(base: Path, name: str, content: str | None = None) -> Path:
    skill_dir = base / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        content
        or f"---\nname: {name}\ndescription: desc of {name}\n---\nDo {name}.\n",
        encoding="utf-8",
    )
    return skill_dir


class TestDynamicRuntimeEnvironmentSkills:
    def test_list_skills_finds_dirs_with_skill_md(self, tmp_path: Path):
        config_dir = tmp_path / "config"
        skills_dir = config_dir / "skills"
        _make_skill_dir(skills_dir, "b-skill")
        _make_skill_dir(skills_dir, "a-skill")
        (skills_dir / "not-a-skill").mkdir()  # dir without SKILL.md
        (skills_dir / "stray.md").write_text("not a dir", encoding="utf-8")

        env = DynamicRuntimeEnvironment(config_dir, tmp_path / "data")
        assert env.list_skills() == ["a-skill", "b-skill"]

    def test_list_skills_missing_dir_returns_empty(self, tmp_path: Path):
        env = DynamicRuntimeEnvironment(tmp_path / "config", tmp_path / "data")
        assert env.list_skills() == []

    def test_load_skill_parses_file_with_dir_name_fallback(self, tmp_path: Path):
        config_dir = tmp_path / "config"
        _make_skill_dir(
            config_dir / "skills",
            "pdf",
            "---\ndescription: PDF stuff\n---\nUse pdf tools.\n",
        )
        env = DynamicRuntimeEnvironment(config_dir, tmp_path / "data")
        skill = env.load_skill("pdf", MagicMock())
        assert isinstance(skill, Skill)
        assert skill.name == "pdf"  # fallback to dir name
        assert skill.description == "PDF stuff"
        assert skill.instructions == "Use pdf tools."

    def test_load_skill_missing_raises(self, tmp_path: Path):
        env = DynamicRuntimeEnvironment(tmp_path / "config", tmp_path / "data")
        with pytest.raises(ValueError, match="Invalid skill name"):
            env.load_skill("nope", MagicMock())


# ---------------------------------------------------------------------------
# StaticRuntimeEnvironment
# ---------------------------------------------------------------------------


class TestStaticRuntimeEnvironmentSkills:
    def _make_env(self, skills: dict[str, Skill] | None = None):
        return StaticRuntimeEnvironment(
            bond_config=BondConfig(),
            providers={},
            personas={},
            plugins={},
            prompts={},
            skills=skills,
        )

    def test_list_and_load_skills(self):
        skill = Skill(name="s", description="d", instructions="i")
        env = self._make_env({"s": skill})
        assert env.list_skills() == ["s"]
        assert env.load_skill("s", MagicMock()) is skill

    def test_skills_default_to_empty(self):
        env = self._make_env()
        assert env.list_skills() == []


# ---------------------------------------------------------------------------
# BondRuntime skill cache
# ---------------------------------------------------------------------------


class TestBondRuntimeSkills:
    def test_get_skill_caches_loads(self):
        skill = Skill(name="cached", description="d", instructions="i")
        env = StaticRuntimeEnvironment(
            bond_config=BondConfig(),
            providers={},
            personas={},
            plugins={},
            prompts={},
            skills={"cached": skill},
        )
        env.load_skill = MagicMock(wraps=env.load_skill)  # type: ignore[method-assign]

        runtime = BondRuntime()
        old_env = runtime._environment
        runtime._environment = env
        try:
            assert runtime.list_skills() == ["cached"]
            first = runtime.get_skill("cached")
            second = runtime.get_skill("cached")
            assert first is skill
            assert second is skill
            env.load_skill.assert_called_once_with("cached", runtime)
        finally:
            runtime._environment = old_env


# ---------------------------------------------------------------------------
# effective_available_skills
# ---------------------------------------------------------------------------


def _persona_config(available_skills: list[str] | None = None) -> PersonaConfig:
    return PersonaConfig(
        name="p",
        generation={},
        available_skills=available_skills if available_skills is not None else [],
    )


class TestEffectiveAvailableSkills:
    def test_conversation_list_wins_over_persona(self):
        conv = Conversation(available_skills=["a", "b"])
        persona = _persona_config(["c"])
        assert effective_available_skills(conv, persona) == ["a", "b"]

    def test_conversation_none_falls_back_to_persona_config(self):
        conv = Conversation()
        persona = _persona_config(["c", "d"])
        assert effective_available_skills(conv, persona) == ["c", "d"]

    def test_accepts_instantiated_persona(self):
        conv = Conversation()
        persona = Persona(
            name="p",
            config=_persona_config(["x"]),
            generation=None,  # type: ignore[arg-type]
            summarization=None,
            thought_condensation=None,
            tts=None,
            memory=None,
            toolbox=None,  # type: ignore[arg-type]
        )
        assert effective_available_skills(conv, persona) == ["x"]

    def test_persona_none_returns_empty(self):
        conv = Conversation()
        assert effective_available_skills(conv, None) == []

    def test_conversation_empty_list_is_explicit_not_none(self):
        conv = Conversation(available_skills=[])
        persona = _persona_config(["c"])
        assert effective_available_skills(conv, persona) == []

    def test_defaults(self):
        conv = Conversation()
        assert conv.available_skills is None
        assert conv.active_skills == []
        assert _persona_config().available_skills == []


# ---------------------------------------------------------------------------
# prune_active_skills
# ---------------------------------------------------------------------------


class TestPruneActiveSkills:
    def test_removes_entries_not_in_available(self):
        conv = Conversation(active_skills=["a", "b", "c"])
        removed = prune_active_skills(conv, ["a", "c"])
        assert removed == ["b"]
        assert conv.active_skills == ["a", "c"]

    def test_noop_when_already_consistent(self):
        conv = Conversation(active_skills=["a", "b"])
        removed = prune_active_skills(conv, ["a", "b", "c"])
        assert removed == []
        assert conv.active_skills == ["a", "b"]

    def test_empty_available_clears_all(self):
        conv = Conversation(active_skills=["a", "b"])
        removed = prune_active_skills(conv, [])
        assert removed == ["a", "b"]
        assert conv.active_skills == []

    def test_empty_active_stays_empty(self):
        conv = Conversation(active_skills=[])
        removed = prune_active_skills(conv, ["a"])
        assert removed == []
        assert conv.active_skills == []

    def test_preserves_order(self):
        conv = Conversation(active_skills=["c", "a", "b"])
        removed = prune_active_skills(conv, ["a", "c", "d"])
        assert removed == ["b"]
        assert conv.active_skills == ["c", "a"]


# ---------------------------------------------------------------------------
# Conversation serialization with skill fields
# ---------------------------------------------------------------------------


class TestConversationSkillFieldsSerialization:
    def test_roundtrip_with_values(self):
        conv = Conversation(available_skills=["a"], active_skills=["b", "c"])
        loaded = Conversation.model_validate_json(conv.model_dump_json())
        assert loaded.available_skills == ["a"]
        assert loaded.active_skills == ["b", "c"]

    def test_old_metadata_without_skill_fields_loads_with_defaults(self):
        # Simulates a conversation saved before the skill fields existed
        old_json = '{"name": "old", "persona": "assistant"}'
        conv = Conversation.model_validate_json(old_json)
        assert conv.available_skills is None
        assert conv.active_skills == []

    def test_roundtrip_defaults(self):
        conv = Conversation()
        loaded = Conversation.model_validate_json(conv.model_dump_json())
        assert loaded.available_skills is None
        assert loaded.active_skills == []
