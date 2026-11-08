"""Tests for skill-provided toolsets: discovery, lazy loading, namespacing,
caching on the Skill instance, and robustness against broken tool files."""

import sys
from pathlib import Path

import pytest
from returns.result import Failure, Success

from bond.config import BondConfig
from bond.runtime import BondRuntime, StaticRuntimeEnvironment
from bond.skill import (
    Skill,
    _discover_tool_files,
    _load_skill_toolsets,
)
from bond.tools import tool
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import (
    ActiveToolset,
    PrefixedToolset,
    PythonToolset,
    Toolbox,
    Toolset,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_context() -> ToolCallContext:
    return ToolCallContext(
        persona=None,
        stdout=None,
        stdin=None,
        is_interactive=False,
        cwd=None,
        logger=None,
        confirmation_prompt=None,
        conversation=None,
    )


def make_skill_dir(base: Path, name: str = "pdf") -> Path:
    skill_dir = base / name
    (skill_dir / "tools").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill\n---\nInstructions.\n",
        encoding="utf-8",
    )
    return skill_dir


def write_tool_file(skill_dir: Path, filename: str, content: str) -> Path:
    path = skill_dir / "tools" / filename
    path.write_text(content, encoding="utf-8")
    return path


def greet_tool_file(greeting: str = "Hello") -> str:
    return f"""
from bond.tools import tool
from bond.tools.toolbox import PythonToolset

@tool.tool(
    name="greet",
    description="Greet someone.",
    parameters={{
        "name": tool.FunctionParameter(type="string", description="Who to greet"),
    }},
    required=["name"],
)
def greet(context, name):
    return "{greeting}, " + name + "!"

EXPORT_TOOLSETS = [PythonToolset("greeters", [greet])]
"""


SIBLING_MAIN = """
import skilltest_helper

from bond.tools import tool
from bond.tools.toolbox import PythonToolset

@tool.tool(
    name="get_value",
    description="Return the helper value.",
    parameters={},
)
def get_value(context):
    return skilltest_helper.VALUE

EXPORT_TOOLSETS = [PythonToolset("vals", [get_value])]
"""

SIBLING_HELPER = 'VALUE = "from-helper"\n'

CUSTOM_TOOLSET_FILE = """
from bond.tools import tool
from bond.tools.toolbox import ActiveToolset, Toolset

@tool.tool(name="ping", description="Ping.", parameters={})
def ping(context):
    return "pong"


class MyToolset(Toolset):
    def __init__(self):
        super().__init__("mine")

    def activate(self):
        return ActiveToolset([ping])


EXPORT_TOOLSETS = [MyToolset()]
"""


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestDiscoverToolFiles:
    def test_accepts_tool_prefixed_and_suffixed(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path)
        for name in ["tool_a.py", "x_tool.py", "x_tools.py"]:
            write_tool_file(skill_dir, name, "")
        found = [f.name for f in _discover_tool_files(skill_dir / "tools")]
        assert found == ["tool_a.py", "x_tool.py", "x_tools.py"]

    @pytest.mark.parametrize(
        "name",
        ["helper.py", "tools.py", "tool.py", "__init__.py", "notes.txt", "tool_.py"],
    )
    def test_rejects_non_tool_files(self, tmp_path: Path, name: str):
        skill_dir = make_skill_dir(tmp_path)
        write_tool_file(skill_dir, name, "")
        assert _discover_tool_files(skill_dir / "tools") == []

    def test_non_recursive_and_sorted(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path)
        write_tool_file(skill_dir, "tool_b.py", "")
        write_tool_file(skill_dir, "tool_a.py", "")
        nested = skill_dir / "tools" / "nested"
        nested.mkdir()
        (nested / "tool_c.py").write_text("", encoding="utf-8")
        found = [f.name for f in _discover_tool_files(skill_dir / "tools")]
        assert found == ["tool_a.py", "tool_b.py"]

    def test_missing_tools_dir_returns_empty(self, tmp_path: Path):
        skill_dir = tmp_path / "s"
        skill_dir.mkdir()
        assert _discover_tool_files(skill_dir / "tools") == []


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


class TestLoadSkillToolsets:
    def test_loads_and_prefixes_toolset_and_tools(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(skill_dir, "tool_greet.py", greet_tool_file())
        toolsets = _load_skill_toolsets(skill_dir, "pdf")
        assert len(toolsets) == 1
        ts = toolsets[0]
        assert isinstance(ts, PrefixedToolset)
        assert ts.name == "sk:pdf:greeters"
        active = ts.activate()
        assert [t.description.function.name for t in active.tools] == ["sk:pdf:greet"]

    def test_export_toolsets_as_callable(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(
            skill_dir,
            "tool_greet.py",
            """
from bond.tools import tool
from bond.tools.toolbox import PythonToolset

@tool.tool(
    name="greet",
    description="Greet.",
    parameters={"name": tool.FunctionParameter(type="string", description="who")},
    required=["name"],
)
def greet(context, name):
    return "Hello, " + name + "!"


def _export():
    return [PythonToolset("greeters", [greet])]


EXPORT_TOOLSETS = _export
""",
        )
        toolsets = _load_skill_toolsets(skill_dir, "pdf")
        assert len(toolsets) == 1
        assert toolsets[0].name == "sk:pdf:greeters"

    def test_multiple_files_sorted(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        for stem, ts_name in [("tool_b", "ts_b"), ("tool_a", "ts_a")]:
            write_tool_file(
                skill_dir,
                f"{stem}.py",
                f"""
from bond.tools import tool
from bond.tools.toolbox import PythonToolset

@tool.tool(name="greet", description="Greet.", parameters={{}})
def greet(context):
    return "hi"

EXPORT_TOOLSETS = [PythonToolset("{ts_name}", [greet])]
""",
            )
        toolsets = _load_skill_toolsets(skill_dir, "pdf")
        assert [ts.name for ts in toolsets] == ["sk:pdf:ts_a", "sk:pdf:ts_b"]

    def test_non_toolset_items_skipped(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(
            skill_dir,
            "tool_greet.py",
            """
from bond.tools import tool
from bond.tools.toolbox import PythonToolset

@tool.tool(name="greet", description="Greet.", parameters={})
def greet(context):
    return "hi"

EXPORT_TOOLSETS = [PythonToolset("ok", [greet]), "not a toolset", 42]
""",
        )
        toolsets = _load_skill_toolsets(skill_dir, "pdf")
        assert [ts.name for ts in toolsets] == ["sk:pdf:ok"]

    def test_missing_export_toolsets_skipped(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(skill_dir, "tool_greet.py", "X = 1\n")
        assert _load_skill_toolsets(skill_dir, "pdf") == []

    def test_empty_export_list(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(skill_dir, "tool_greet.py", "EXPORT_TOOLSETS = []\n")
        assert _load_skill_toolsets(skill_dir, "pdf") == []

    def test_custom_toolset_subclass_passes_through(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(skill_dir, "tool_custom.py", CUSTOM_TOOLSET_FILE)
        toolsets = _load_skill_toolsets(skill_dir, "pdf")
        assert len(toolsets) == 1
        assert isinstance(toolsets[0], PrefixedToolset)
        assert toolsets[0].name == "sk:pdf:mine"

    def test_sibling_imports_work_and_sys_path_restored(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path)
        tools_dir = skill_dir / "tools"
        (tools_dir / "skilltest_helper.py").write_text(SIBLING_HELPER, encoding="utf-8")
        write_tool_file(skill_dir, "tool_main.py", SIBLING_MAIN)
        toolsets = _load_skill_toolsets(skill_dir, "pdf")
        assert len(toolsets) == 1
        bond_tool = toolsets[0].activate().get_tool("sk:pdf:get_value")
        assert bond_tool is not None
        assert bond_tool(make_context()) == "from-helper"
        assert str(tools_dir) not in sys.path


# ---------------------------------------------------------------------------
# Robustness: misconfigured / crashing modules must never propagate
# ---------------------------------------------------------------------------


class TestLoadSkillToolsetsRobustness:
    def test_syntax_error_file_skipped_others_still_load(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(skill_dir, "tool_bad.py", "def broken(:\n")
        write_tool_file(skill_dir, "tool_good.py", greet_tool_file())
        toolsets = _load_skill_toolsets(skill_dir, "pdf")
        assert [ts.name for ts in toolsets] == ["sk:pdf:greeters"]
        assert any("tool_bad.py" in r.getMessage() for r in caplog.records)

    def test_import_time_exception_skipped(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(skill_dir, "tool_bad.py", "raise RuntimeError('boom')\n")
        assert _load_skill_toolsets(skill_dir, "pdf") == []

    def test_system_exit_at_import_is_contained(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(skill_dir, "tool_bad.py", "import sys; sys.exit(3)\n")
        assert _load_skill_toolsets(skill_dir, "pdf") == []

    def test_invalid_utf8_file_skipped(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        (skill_dir / "tools" / "tool_bin.py").write_bytes(b"\xff\xfd\x80 not utf8")
        assert _load_skill_toolsets(skill_dir, "pdf") == []

    def test_export_toolsets_not_iterable_skipped(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(skill_dir, "tool_greet.py", "EXPORT_TOOLSETS = 42\n")
        assert _load_skill_toolsets(skill_dir, "pdf") == []

    def test_export_toolsets_string_skipped(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(skill_dir, "tool_greet.py", 'EXPORT_TOOLSETS = "oops"\n')
        assert _load_skill_toolsets(skill_dir, "pdf") == []

    def test_callable_export_raising_skipped(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(
            skill_dir,
            "tool_greet.py",
            "def _e():\n    raise ValueError('nope')\n\nEXPORT_TOOLSETS = _e\n",
        )
        assert _load_skill_toolsets(skill_dir, "pdf") == []

    def test_no_tools_dir(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        (skill_dir / "tools").rmdir()
        assert _load_skill_toolsets(skill_dir, "pdf") == []

    def test_tools_path_is_a_file(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        (skill_dir / "tools").rmdir()
        (skill_dir / "tools").write_text("x", encoding="utf-8")
        assert _load_skill_toolsets(skill_dir, "pdf") == []

    def test_failed_import_not_left_in_sys_modules(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        write_tool_file(skill_dir, "tool_bad.py", "raise RuntimeError('boom')\n")
        _load_skill_toolsets(skill_dir, "pdf")
        assert "bond_skilltool_pdf_tool_bad" not in sys.modules


# ---------------------------------------------------------------------------
# Caching: loading the same skill multiple times
# ---------------------------------------------------------------------------


class TestSkillToolsetsCaching:
    def test_same_skill_instance_caches_toolsets(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path)
        write_tool_file(skill_dir, "tool_greet.py", greet_tool_file())
        skill = Skill(name="pdf", description="d", instructions="i", path=skill_dir)
        first = skill.toolsets
        module_after_first = sys.modules["bond_skilltool_pdf_tool_greet"]
        second = skill.toolsets
        assert first is second
        # No re-import happened on the second access
        assert sys.modules["bond_skilltool_pdf_tool_greet"] is module_after_first

    def test_new_skill_instance_reimports(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path)
        write_tool_file(skill_dir, "tool_greet.py", greet_tool_file())
        skill1 = Skill.load_from(skill_dir, "pdf").unwrap()
        toolsets1 = skill1.toolsets
        mod1 = sys.modules["bond_skilltool_pdf_tool_greet"]
        skill2 = Skill.load_from(skill_dir, "pdf").unwrap()
        toolsets2 = skill2.toolsets
        mod2 = sys.modules["bond_skilltool_pdf_tool_greet"]
        assert skill1 is not skill2
        assert toolsets1 is not toolsets2
        assert mod1 is not mod2  # module was executed again

    def test_skill_without_path_has_no_toolsets(self):
        skill = Skill(name="s", description="", instructions="")
        assert skill.toolsets == []
        assert skill.toolsets == []  # stable, no error

    def test_runtime_caches_skill_and_thus_its_toolsets(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "rtcache")
        write_tool_file(skill_dir, "tool_greet.py", greet_tool_file())
        skill = Skill(name="rtcache", description="d", instructions="i", path=skill_dir)
        env = StaticRuntimeEnvironment(
            bond_config=BondConfig(),
            providers={},
            personas={},
            plugins={},
            prompts={},
            skills={"rtcache": skill},
        )
        runtime = BondRuntime()
        old_env = runtime._environment
        runtime._environment = env
        try:
            r1 = runtime.get_skill("rtcache")
            r2 = runtime.get_skill("rtcache")
            assert isinstance(r1, Success) and isinstance(r2, Success)
            s1, s2 = r1.unwrap(), r2.unwrap()
            assert s1 is s2 is skill
            assert s1.toolsets is s2.toolsets  # imported only once
        finally:
            runtime._environment = old_env


# ---------------------------------------------------------------------------
# PrefixedToolset
# ---------------------------------------------------------------------------


class TestPrefixedToolset:
    def _make_toolset(self) -> PythonToolset:
        @tool.tool(
            name="greet",
            description="Greet.",
            parameters={
                "name": tool.FunctionParameter(type="string", description="who")
            },
            required=["name"],
        )
        def greet(context, name):
            return f"Hello, {name}!"

        return PythonToolset("greeters", [greet])

    def test_activate_prefixes_names_without_mutating_original(self):
        ts = self._make_toolset()
        wrapped = PrefixedToolset(ts, "sk:pdf:")
        assert wrapped.name == "sk:pdf:greeters"
        assert ts.name == "greeters"  # original untouched
        active = wrapped.activate()
        assert [t.description.function.name for t in active.tools] == ["sk:pdf:greet"]
        assert [t.function.name for t in ts.tool_descriptions] == ["greet"]

    def test_execution_routes_to_original_function(self):
        wrapped = PrefixedToolset(self._make_toolset(), "sk:pdf:")
        bond_tool = wrapped.activate().get_tool("sk:pdf:greet")
        assert bond_tool is not None
        assert bond_tool(make_context(), name="World") == "Hello, World!"

    def test_release_delegates_to_wrapped_active_toolset(self):
        class RecordingActive(ActiveToolset):
            def __init__(self):
                super().__init__([])
                self.released = False

            def release(self):
                self.released = True

        class RecordingToolset(Toolset):
            def __init__(self):
                super().__init__("rec")
                self.active = RecordingActive()

            def activate(self):
                return self.active

        rec = RecordingToolset()
        active = PrefixedToolset(rec, "sk:x:").activate()
        assert not rec.active.released
        active.release()
        assert rec.active.released


# ---------------------------------------------------------------------------
# Skill.load_from
# ---------------------------------------------------------------------------


class TestSkillLoadFrom:
    def test_success_sets_path(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, "pdf")
        result = Skill.load_from(skill_dir, "pdf")
        assert isinstance(result, Success)
        skill = result.unwrap()
        assert skill.path == skill_dir
        assert skill.name == "pdf"

    def test_missing_skill_md_fails_with_path_in_message(self, tmp_path: Path):
        result = Skill.load_from(tmp_path / "nope", "nope")
        assert isinstance(result, Failure)
        assert str(tmp_path / "nope") in result.failure()


# ---------------------------------------------------------------------------
# Integration with Toolbox
# ---------------------------------------------------------------------------


class TestSkillToolsetsInToolbox:
    def test_add_call_remove(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path)
        write_tool_file(skill_dir, "tool_greet.py", greet_tool_file())
        (toolset,) = _load_skill_toolsets(skill_dir, "pdf")
        toolbox = Toolbox([])
        toolbox.add_toolset(toolset)
        assert toolbox.has_tool("sk:pdf:greet")
        assert [t.function.name for t in toolbox.tool_descriptions] == ["sk:pdf:greet"]
        result = toolbox.call_tool("sk:pdf:greet", {"name": "World"}, make_context())
        assert result.unwrap() == "Hello, World!"
        toolbox.remove_toolset("sk:pdf:greeters")
        assert not toolbox.has_tool("sk:pdf:greet")
        assert toolbox.tool_descriptions == []

    def test_adding_same_toolset_twice_raises(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path)
        write_tool_file(skill_dir, "tool_greet.py", greet_tool_file())
        (toolset,) = _load_skill_toolsets(skill_dir, "pdf")
        toolbox = Toolbox([])
        toolbox.add_toolset(toolset)
        with pytest.raises(ValueError):
            toolbox.add_toolset(toolset)

    def test_two_skills_with_same_tool_name_do_not_collide(self, tmp_path: Path):
        dir_a = make_skill_dir(tmp_path, "alpha")
        dir_b = make_skill_dir(tmp_path, "beta")
        write_tool_file(dir_a, "tool_greet.py", greet_tool_file("Hi from alpha"))
        write_tool_file(dir_b, "tool_greet.py", greet_tool_file("Yo from beta"))
        toolbox = Toolbox([])
        for skill_dir, skill_name in [(dir_a, "alpha"), (dir_b, "beta")]:
            for ts in _load_skill_toolsets(skill_dir, skill_name):
                toolbox.add_toolset(ts)
        assert toolbox.has_tool("sk:alpha:greet")
        assert toolbox.has_tool("sk:beta:greet")
        r_a = toolbox.call_tool("sk:alpha:greet", {"name": "X"}, make_context())
        r_b = toolbox.call_tool("sk:beta:greet", {"name": "X"}, make_context())
        assert r_a.unwrap() == "Hi from alpha, X!"
        assert r_b.unwrap() == "Yo from beta, X!"
