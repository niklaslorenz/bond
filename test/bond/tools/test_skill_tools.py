"""Tests for bond.tools.skill_tools (load_skill / unload_skill)."""

from unittest.mock import MagicMock

from bond.conversation.conversation import Conversation
from bond.persona import Persona, PersonaConfig
from bond.runtime import BondRuntime, _default_toolsets
from bond.skill import Skill
from bond.tools.skill_tools import load_skill, unload_skill
from bond.tools.tool import ToolCallContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_persona(available_skills: list[str]) -> Persona:
    return Persona(
        name="p",
        config=PersonaConfig(
            name="p", generation={}, available_skills=available_skills
        ),
        generation=None,  # type: ignore[arg-type]
        summarization=None,
        thought_condensation=None,
        tts=None,
        memory=None,
        toolbox=None,  # type: ignore[arg-type]
    )


def make_context(
    conversation: Conversation | None,
    persona: Persona | None = None,
) -> ToolCallContext:
    return ToolCallContext(
        persona=persona,
        stdout=None,
        stdin=None,
        is_interactive=False,
        cwd=None,
        logger=None,
        confirmation_prompt=None,
        conversation=conversation,
    )


def patch_runtime(monkeypatch, skills: dict[str, Skill]):
    """Patch BondRuntime.get_instance() to return a mock serving `skills`."""
    runtime = MagicMock()
    runtime.get_skill.side_effect = lambda name: skills[name]
    get_instance = MagicMock(return_value=runtime)
    monkeypatch.setattr(BondRuntime, "get_instance", get_instance)
    return runtime


SKILL_PDF = Skill(
    name="pdf", description="PDF tools", instructions="Use pdf tools when asked."
)
SKILL_GIT = Skill(
    name="git", description="Git helpers", instructions="Use git helpers when asked."
)


# ---------------------------------------------------------------------------
# Toolset registration
# ---------------------------------------------------------------------------


class TestSkillsToolsetRegistered:
    def test_skills_toolset_is_builtin(self):
        toolset_names = [toolset.name for toolset in _default_toolsets]
        assert "skills" in toolset_names

    def test_skills_toolset_contains_load_and_unload(self):
        toolset = next(t for t in _default_toolsets if t.name == "skills")
        names = [tool.function.name for tool in toolset.tool_descriptions]
        assert "load_skill" in names
        assert "unload_skill" in names


# ---------------------------------------------------------------------------
# load_skill
# ---------------------------------------------------------------------------


class TestLoadSkill:
    def test_no_conversation_returns_error(self, monkeypatch):
        patch_runtime(monkeypatch, {"pdf": SKILL_PDF})
        context = make_context(None, make_persona(["pdf"]))

        result = load_skill(context, name="pdf")

        assert isinstance(result, str)
        assert "Error" in result
        assert "No conversation context" in result

    def test_denied_skill_lists_available(self, monkeypatch):
        patch_runtime(monkeypatch, {"pdf": SKILL_PDF, "git": SKILL_GIT})
        conv = Conversation()
        context = make_context(conv, make_persona(["pdf", "git"]))

        result = load_skill(context, name="secret-skill")

        assert "Error" in result
        assert "secret-skill" in result
        assert "pdf" in result and "git" in result
        assert conv.active_skills == []

    def test_denied_when_no_skills_available(self, monkeypatch):
        patch_runtime(monkeypatch, {"pdf": SKILL_PDF})
        conv = Conversation()
        context = make_context(conv, make_persona([]))

        result = load_skill(context, name="pdf")

        assert "Error" in result
        assert "No skills are available" in result
        assert conv.active_skills == []

    def test_allowed_via_persona_list(self, monkeypatch):
        patch_runtime(monkeypatch, {"pdf": SKILL_PDF})
        conv = Conversation()
        context = make_context(conv, make_persona(["pdf"]))

        result = load_skill(context, name="pdf")

        assert conv.active_skills == ["pdf"]
        assert "activated" in result
        # The skill content must NOT be duplicated into the tool result — it
        # lives in the system prompt (rendered by the system message builder).
        assert "Use pdf tools when asked." not in result
        assert "name: pdf" not in result

    def test_conversation_list_overrides_persona(self, monkeypatch):
        patch_runtime(monkeypatch, {"git": SKILL_GIT})
        conv = Conversation(available_skills=["git"])
        context = make_context(conv, make_persona(["pdf"]))

        result = load_skill(context, name="git")

        assert conv.active_skills == ["git"]
        assert "Error" not in result

    def test_conversation_empty_list_denies_everything(self, monkeypatch):
        patch_runtime(monkeypatch, {"pdf": SKILL_PDF})
        conv = Conversation(available_skills=[])
        context = make_context(conv, make_persona(["pdf"]))

        result = load_skill(context, name="pdf")

        assert "Error" in result
        assert conv.active_skills == []

    def test_works_without_persona_when_conversation_lists_skill(self, monkeypatch):
        patch_runtime(monkeypatch, {"pdf": SKILL_PDF})
        conv = Conversation(available_skills=["pdf"])
        context = make_context(conv, persona=None)

        result = load_skill(context, name="pdf")

        assert conv.active_skills == ["pdf"]
        assert "Error" not in result

    def test_load_is_idempotent(self, monkeypatch):
        patch_runtime(monkeypatch, {"pdf": SKILL_PDF})
        conv = Conversation()
        context = make_context(conv, make_persona(["pdf"]))

        first = load_skill(context, name="pdf")
        second = load_skill(context, name="pdf")

        assert conv.active_skills == ["pdf"]  # no duplicate
        assert "already active" in second
        assert "Use pdf tools when asked." not in second
        assert "activated" in first and "already" not in first

    def test_runtime_error_is_returned_not_raised(self, monkeypatch):
        runtime = MagicMock()
        runtime.get_skill.side_effect = ValueError("Invalid skill name: ghost")
        get_instance = MagicMock(return_value=runtime)
        monkeypatch.setattr(BondRuntime, "get_instance", get_instance)
        conv = Conversation()
        context = make_context(conv, make_persona(["ghost"]))

        result = load_skill(context, name="ghost")

        assert "Error" in result
        assert "ghost" in result
        assert conv.active_skills == []  # not activated on load failure


# ---------------------------------------------------------------------------
# unload_skill
# ---------------------------------------------------------------------------


class TestUnloadSkill:
    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = unload_skill(context, name="pdf")

        assert "Error" in result
        assert "No conversation context" in result

    def test_unload_active_skill(self):
        conv = Conversation(active_skills=["pdf", "git"])
        context = make_context(conv, make_persona(["pdf", "git"]))

        result = unload_skill(context, name="pdf")

        assert conv.active_skills == ["git"]
        assert "unloaded" in result
        assert "git" in result

    def test_unload_last_skill(self):
        conv = Conversation(active_skills=["pdf"])
        context = make_context(conv, make_persona(["pdf"]))

        result = unload_skill(context, name="pdf")

        assert conv.active_skills == []
        assert "unloaded" in result
        assert "No skills are active anymore" in result

    def test_unload_inactive_skill_lists_active(self):
        conv = Conversation(active_skills=["git"])
        context = make_context(conv, make_persona(["pdf", "git"]))

        result = unload_skill(context, name="pdf")

        assert "Error" in result
        assert "not active" in result
        assert "git" in result
        assert conv.active_skills == ["git"]  # unchanged

    def test_unload_inactive_skill_when_none_active(self):
        conv = Conversation()
        context = make_context(conv, make_persona(["pdf"]))

        result = unload_skill(context, name="pdf")

        assert "Error" in result
        assert "No skills are active" in result


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


class TestSkillToolWorkflows:
    def test_load_unload_roundtrip(self, monkeypatch):
        patch_runtime(monkeypatch, {"pdf": SKILL_PDF})
        conv = Conversation()
        context = make_context(conv, make_persona(["pdf"]))

        load_result = load_skill(context, name="pdf")
        assert conv.active_skills == ["pdf"]
        assert "activated" in load_result
        assert "Use pdf tools when asked." not in load_result

        unload_result = unload_skill(context, name="pdf")
        assert conv.active_skills == []
        assert "unloaded" in unload_result

    def test_active_skills_survive_serialization(self, monkeypatch):
        patch_runtime(monkeypatch, {"pdf": SKILL_PDF})
        conv = Conversation()
        context = make_context(conv, make_persona(["pdf"]))
        load_skill(context, name="pdf")

        loaded = Conversation.model_validate_json(conv.model_dump_json())
        assert loaded.active_skills == ["pdf"]
