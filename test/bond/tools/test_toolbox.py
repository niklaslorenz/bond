"""Tests for bond.tools.toolbox: ActiveToolset, PythonToolset, Toolbox,
prefix_tool_description, PrefixedToolset / ActivePrefixedToolset."""

import json

import pytest
from returns.result import Failure

from bond.tools import tool
from bond.tools.tool import BondTool, ToolCallContext
from bond.tools.toolbox import (
    ActivePrefixedToolset,
    ActiveToolset,
    PrefixedToolset,
    PythonToolset,
    Toolbox,
    Toolset,
    prefix_tool_description,
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


def make_tool(name: str, fn=None) -> BondTool:
    if fn is None:

        def fn(context):
            return f"called {name}"

    @tool.tool(name=name, description=f"{name} tool.", parameters={})
    def wrapped(context):
        return fn(context)

    return wrapped


def make_toolset(name: str, *tool_names: str) -> PythonToolset:
    return PythonToolset(name, [make_tool(t) for t in tool_names])


# ---------------------------------------------------------------------------
# ActiveToolset
# ---------------------------------------------------------------------------


class TestActiveToolset:
    def test_tools_returns_a_copy(self):
        t = make_tool("a")
        active = ActiveToolset([t])
        tools = active.tools
        assert tools == [t]
        tools.append(make_tool("b"))
        assert active.tools == [t]

    def test_tool_descriptions(self):
        active = ActiveToolset([make_tool("a"), make_tool("b")])
        assert [t.function.name for t in active.tool_descriptions] == ["a", "b"]

    def test_get_tool(self):
        t = make_tool("a")
        active = ActiveToolset([t])
        assert active.get_tool("a") is t
        assert active.get_tool("nope") is None

    def test_release_is_noop_by_default(self):
        ActiveToolset([]).release()  # must not raise


# ---------------------------------------------------------------------------
# PythonToolset
# ---------------------------------------------------------------------------


class TestPythonToolset:
    def test_name(self):
        assert make_toolset("ts", "a").name == "ts"

    def test_activate_returns_active_toolset_with_same_tools(self):
        ts = make_toolset("ts", "a", "b")
        active = ts.activate()
        assert isinstance(active, ActiveToolset)
        assert [t.description.function.name for t in active.tools] == ["a", "b"]

    def test_tool_descriptions(self):
        ts = make_toolset("ts", "a")
        assert [t.function.name for t in ts.tool_descriptions] == ["a"]

    def test_get_tool_description(self):
        ts = make_toolset("ts", "a")
        desc = ts.get_tool_description("a")
        assert desc is not None
        assert desc.function.name == "a"
        assert ts.get_tool_description("nope") is None


class TestToolsetABC:
    def test_cannot_instantiate_without_activate(self):
        with pytest.raises(TypeError):
            Toolset("x")  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# prefix_tool_description
# ---------------------------------------------------------------------------


class TestPrefixToolDescription:
    def test_prefixes_function_name(self):
        desc = make_tool("greet").description
        prefixed = prefix_tool_description(desc, "sk:pdf:")
        assert prefixed.function.name == "sk:pdf:greet"

    def test_preserves_other_fields(self):
        desc = make_tool("greet").description
        prefixed = prefix_tool_description(desc, "sk:pdf:")
        assert prefixed.function.description == desc.function.description
        assert prefixed.function.parameters == desc.function.parameters
        assert prefixed.type == desc.type

    def test_original_not_mutated(self):
        desc = make_tool("greet").description
        prefix_tool_description(desc, "sk:pdf:")
        assert desc.function.name == "greet"


# ---------------------------------------------------------------------------
# PrefixedToolset / ActivePrefixedToolset
# ---------------------------------------------------------------------------


class RecordingActive(ActiveToolset):
    def __init__(self):
        super().__init__([])
        self.released = False

    def release(self):
        self.released = True


class RecordingToolset(Toolset):
    def __init__(self, name: str = "rec"):
        super().__init__(name)
        self.active = RecordingActive()
        self.activate_calls = 0

    def activate(self):
        self.activate_calls += 1
        return self.active


class TestPrefixedToolset:
    def test_name_is_prefixed(self):
        assert PrefixedToolset(make_toolset("base", "a"), "sk:x:").name == "sk:x:base"

    def test_activate_returns_active_prefixed_toolset(self):
        wrapped = PrefixedToolset(make_toolset("base", "a"), "sk:x:")
        active = wrapped.activate()
        assert isinstance(active, ActivePrefixedToolset)
        assert isinstance(active, ActiveToolset)

    def test_activate_prefixes_tool_names(self):
        wrapped = PrefixedToolset(make_toolset("base", "a", "b"), "sk:x:")
        active = wrapped.activate()
        assert [t.description.function.name for t in active.tools] == [
            "sk:x:a",
            "sk:x:b",
        ]
        assert active.get_tool("sk:x:a") is not None
        assert active.get_tool("a") is None

    def test_original_toolset_not_mutated(self):
        ts = make_toolset("base", "a")
        PrefixedToolset(ts, "sk:x:").activate()
        assert ts.name == "base"
        assert [t.function.name for t in ts.tool_descriptions] == ["a"]

    def test_execution_routes_to_original_function(self):
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

        wrapped = PrefixedToolset(PythonToolset("base", [greet]), "sk:x:")
        bond_tool = wrapped.activate().get_tool("sk:x:greet")
        assert bond_tool is not None
        assert bond_tool(make_context(), name="World") == "Hello, World!"

    def test_release_delegates_to_wrapped_active_toolset(self):
        rec = RecordingToolset()
        active = PrefixedToolset(rec, "sk:x:").activate()
        assert rec.activate_calls == 1
        assert not rec.active.released
        active.release()
        assert rec.active.released

    def test_each_activate_calls_wrapped_activate(self):
        rec = RecordingToolset()
        wrapped = PrefixedToolset(rec, "sk:x:")
        wrapped.activate()
        wrapped.activate()
        assert rec.activate_calls == 2


# ---------------------------------------------------------------------------
# Toolbox
# ---------------------------------------------------------------------------


class TestToolboxConstruction:
    def test_empty(self):
        toolbox = Toolbox([])
        assert toolbox.tool_descriptions == []
        assert toolbox.toolset_names == []
        assert toolbox.toolsets == []
        assert not toolbox.has_tool("anything")

    def test_multiple_toolsets(self):
        toolbox = Toolbox([make_toolset("ts1", "a"), make_toolset("ts2", "b")])
        assert toolbox.toolset_names == ["ts1", "ts2"]
        assert sorted(t.function.name for t in toolbox.tool_descriptions) == ["a", "b"]
        assert toolbox.has_tool("a") and toolbox.has_tool("b")

    def test_duplicate_tool_name_across_toolsets_raises(self):
        with pytest.raises(ValueError, match="Duplicate tool name"):
            Toolbox([make_toolset("ts1", "a"), make_toolset("ts2", "a")])

    def test_duplicate_toolset_name_last_wins(self):
        # dict semantics: {"ts": ...} — later toolset overwrites the earlier one
        toolbox = Toolbox([make_toolset("ts", "a"), make_toolset("ts", "b")])
        assert toolbox.toolset_names == ["ts"]
        assert [t.function.name for t in toolbox.tool_descriptions] == ["b"]

    def test_toolsets_property_returns_toolsets(self):
        ts1, ts2 = make_toolset("ts1", "a"), make_toolset("ts2", "b")
        toolbox = Toolbox([ts1, ts2])
        assert toolbox.toolsets == [ts1, ts2]


class TestToolboxAddRemove:
    def test_add_toolset(self):
        toolbox = Toolbox([])
        ts = make_toolset("ts", "a")
        active = toolbox.add_toolset(ts)
        assert isinstance(active, ActiveToolset)
        assert toolbox.has_tool("a")
        assert toolbox.toolset_names == ["ts"]
        assert [t.function.name for t in toolbox.tool_descriptions] == ["a"]

    def test_add_duplicate_toolset_name_raises(self):
        toolbox = Toolbox([make_toolset("ts", "a")])
        with pytest.raises(ValueError, match="Duplicate toolset name"):
            toolbox.add_toolset(make_toolset("ts", "b"))

    def test_add_duplicate_tool_name_raises_and_is_atomic(self):
        toolbox = Toolbox([make_toolset("ts1", "a")])
        with pytest.raises(ValueError, match="Duplicate tool name"):
            toolbox.add_toolset(make_toolset("ts2", "a", "b"))
        # nothing from ts2 was registered
        assert toolbox.toolset_names == ["ts1"]
        assert not toolbox.has_tool("b")
        assert [t.function.name for t in toolbox.tool_descriptions] == ["a"]

    def test_remove_toolset(self):
        toolbox = Toolbox([make_toolset("ts", "a")])
        toolbox.remove_toolset("ts")
        assert toolbox.toolset_names == []
        assert not toolbox.has_tool("a")
        assert toolbox.tool_descriptions == []

    def test_remove_unknown_toolset_is_noop(self):
        toolbox = Toolbox([make_toolset("ts", "a")])
        toolbox.remove_toolset("nope")  # must not raise
        assert toolbox.has_tool("a")

    def test_remove_toolset_releases_active(self):
        rec = RecordingToolset("rec")
        toolbox = Toolbox([rec])
        toolbox.remove_toolset("rec")
        assert rec.active.released

    def test_remove_one_of_several(self):
        toolbox = Toolbox([make_toolset("ts1", "a"), make_toolset("ts2", "b")])
        toolbox.remove_toolset("ts1")
        assert toolbox.toolset_names == ["ts2"]
        assert not toolbox.has_tool("a")
        assert toolbox.has_tool("b")


class TestToolboxRelease:
    def test_release_releases_all_active_toolsets(self):
        rec1, rec2 = RecordingToolset("r1"), RecordingToolset("r2")
        toolbox = Toolbox([rec1, rec2])
        toolbox.release()
        assert rec1.active.released and rec2.active.released

    def test_after_release_tools_can_be_called_again(self):
        # _find_tool lazily re-activates a released toolset
        ts = make_toolset("ts", "a")
        toolbox = Toolbox([ts])
        toolbox.release()
        assert toolbox.has_tool("a")  # registration survives release
        result = toolbox.call_tool("a", {}, make_context())
        assert result.unwrap() == "called a"


class TestToolboxCallTool:
    def test_string_result(self):
        toolbox = Toolbox([make_toolset("ts", "a")])
        assert toolbox.call_tool("a", {}, make_context()).unwrap() == "called a"

    def test_none_result(self):
        @tool.tool(name="noop", description="Does nothing.", parameters={})
        def noop(context):
            return None

        toolbox = Toolbox([PythonToolset("ts", [noop])])
        assert toolbox.call_tool("noop", {}, make_context()).unwrap() == (
            "Success (no output)"
        )

    def test_dict_result_is_json_serialized(self):
        @tool.tool(name="data", description="Returns data.", parameters={})
        def data(context):
            return {"x": 1}

        toolbox = Toolbox([PythonToolset("ts", [data])])
        result = toolbox.call_tool("data", {}, make_context()).unwrap()
        assert json.loads(result) == {"x": 1}

    def test_arguments_are_passed_through(self):
        @tool.tool(
            name="echo",
            description="Echo.",
            parameters={
                "text": tool.FunctionParameter(type="string", description="text")
            },
            required=["text"],
        )
        def echo(context, text):
            return f"echo: {text}"

        toolbox = Toolbox([PythonToolset("ts", [echo])])
        result = toolbox.call_tool("echo", {"text": "hi"}, make_context())
        assert result.unwrap() == "echo: hi"

    def test_unknown_tool_fails(self):
        toolbox = Toolbox([make_toolset("ts", "a")])
        result = toolbox.call_tool("nope", {}, make_context())
        assert isinstance(result, Failure)
        assert result.failure() == "Invalid tool name"

    def test_exception_in_tool_fails_with_message(self):
        @tool.tool(name="boom", description="Raises.", parameters={})
        def boom(context):
            raise ValueError("kaput")

        toolbox = Toolbox([PythonToolset("ts", [boom])])
        result = toolbox.call_tool("boom", {}, make_context())
        assert isinstance(result, Failure)
        assert "kaput" in result.failure()
        assert "ValueError" in result.failure()

    def test_call_prefixed_tool_from_prefixed_toolset(self):
        ts = PrefixedToolset(make_toolset("base", "a"), "sk:x:")
        toolbox = Toolbox([ts])
        assert toolbox.has_tool("sk:x:a")
        assert not toolbox.has_tool("a")
        result = toolbox.call_tool("sk:x:a", {}, make_context())
        assert result.unwrap() == "called a"
