"""Tests for bond.tools.local_tools (list_local_scripts / run_local_script)."""

import stat
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bond.runtime import BondRuntime, _default_toolsets
from bond.tools.local_tools import list_local_scripts, run_local_script
from bond.tools.tool import ToolCallContext


def make_context(cwd: Path | None) -> ToolCallContext:
    return ToolCallContext(
        persona=None,
        stdout=None,
        stdin=None,
        is_interactive=False,
        cwd=cwd,
        logger=None,
        confirmation_prompt=None,
        conversation=None,
    )


@pytest.fixture
def project(tmp_path: Path, monkeypatch):
    """A fake project with .bond/scripts, served by a mocked runtime singleton."""
    bond_dir = tmp_path / ".bond"
    scripts = bond_dir / "scripts"
    scripts.mkdir(parents=True)
    runtime = MagicMock()
    runtime.get_local_bond_dir.return_value = bond_dir
    runtime.get_local_scripts_path.return_value = scripts
    monkeypatch.setattr(BondRuntime, "get_instance", MagicMock(return_value=runtime))
    return tmp_path, bond_dir, scripts, runtime


class TestToolsetRegistered:
    def test_local_toolset_is_builtin(self, project):
        toolset_names = [toolset.name for toolset in _default_toolsets]
        assert "local" in toolset_names

    def test_local_toolset_contains_both_tools(self, project):
        toolset = next(t for t in _default_toolsets if t.name == "local")
        names = [tool.function.name for tool in toolset.tool_descriptions]
        assert "list_local_scripts" in names
        assert "run_local_script" in names


class TestListLocalScripts:
    def test_no_bond_dir(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        runtime.get_local_bond_dir.return_value = None
        runtime.get_local_scripts_path.return_value = None
        result = list_local_scripts(make_context(tmp_path))
        assert "no local `.bond`" in result

    def test_no_scripts_dir(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        scripts.rmdir()
        result = list_local_scripts(make_context(tmp_path))
        assert "No scripts directory" in result

    def test_lists_scripts_with_description(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        (scripts / "hello.sh").write_text(
            "# Runs the tests\n#!/bin/sh\n", encoding="utf-8"
        )
        (scripts / "deploy.py").write_text("import sys\n", encoding="utf-8")
        result = list_local_scripts(make_context(tmp_path))
        assert "hello.sh" in result
        assert "Runs the tests" in result
        assert "deploy.py" in result


class TestRunLocalScript:
    def test_no_bond_dir(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        runtime.get_local_bond_dir.return_value = None
        result = run_local_script(make_context(tmp_path), "x")
        assert "no local `.bond`" in result

    def test_invalid_names_rejected(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        for name in ("a/b", "..", "../x", ".hidden/x", "sub\\win"):
            result = run_local_script(make_context(tmp_path), name)
            assert "invalid script name" in result, name

    def test_nonexistent_script(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        result = run_local_script(make_context(tmp_path), "missing")
        assert "no such script" in result

    def test_symlink_escape_rejected(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        outside = tmp_path / "outside"
        outside.write_text("evil", encoding="utf-8")
        (scripts / "link").symlink_to(outside)
        result = run_local_script(make_context(tmp_path), "link")
        assert "outside" in result

    def test_run_py_script_with_args(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        script = scripts / "test.py"
        script.write_text(
            "import sys\nprint('hello', sys.argv[1])\n", encoding="utf-8"
        )
        result = run_local_script(make_context(tmp_path), "test.py", args=["world"])
        assert "exit code: 0" in result
        assert "hello world" in result

    def test_run_sh_script(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        script = scripts / "test.sh"
        script.write_text("# desc\n#!/bin/sh\necho sh-$1\n", encoding="utf-8")
        result = run_local_script(make_context(tmp_path), "test.sh", args=["x"])
        assert "exit code: 0" in result
        assert "sh-x" in result

    def test_run_executable_file(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        script = scripts / "hi"
        script.write_text("#!/bin/sh\necho hi-output\n", encoding="utf-8")
        script.chmod(stat.S_IEXEC | stat.S_IREAD)
        result = run_local_script(make_context(tmp_path), "hi")
        assert "exit code: 0" in result
        assert "hi-output" in result

    def test_failing_script_reports_exit_code(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        script = scripts / "fail.py"
        script.write_text(
            f"import sys\nprint('oops', file=sys.stderr)\nsys.exit(3)\n",
            encoding="utf-8",
        )
        result = run_local_script(make_context(tmp_path), "fail.py")
        assert "exit code: 3" in result
        assert "oops" in result

    def test_timeout(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        script = scripts / "slow.py"
        script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        result = run_local_script(make_context(tmp_path), "slow.py", timeout=1)
        assert "timed out" in result

    def test_runs_in_project_root(self, project):
        tmp_path, bond_dir, scripts, runtime = project
        script = scripts / "pwd.py"
        script.write_text("import os\nprint(os.getcwd())\n", encoding="utf-8")
        result = run_local_script(make_context(tmp_path), "pwd.py")
        assert str(tmp_path) in result or str(tmp_path.resolve()) in result
