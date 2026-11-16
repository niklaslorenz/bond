"""Tests for the unified file-system access layer in bond.fs_access."""

from pathlib import Path
from unittest.mock import MagicMock

from returns.result import Failure, Success

from bond.fs_access import (
    AccessMode,
    AuthorizedPath,
    classify,
    path_is_in_bond,
    path_is_in_git,
    request_fs_access,
    Denied,
    NeedsConfirmation,
    PreAuthorized,
)
from bond.persona import ManagedDirectory, Persona, PersonaConfig
from bond.tools.tool import ToolCallContext


def make_context(
    cwd: Path | None,
    is_interactive: bool = False,
    confirm: bool = True,
    prompts: list[str] | None = None,
    persona: Persona | None = None,
) -> ToolCallContext:
    def confirmation_prompt(prompt: str) -> bool:
        if prompts is not None:
            prompts.append(prompt)
        return confirm

    return ToolCallContext(
        persona=persona,
        stdout=None,
        stdin=None,
        is_interactive=is_interactive,
        cwd=cwd,
        logger=None,
        confirmation_prompt=confirmation_prompt,
        conversation=None,
    )


def make_persona(root: Path, read_only: bool = False) -> Persona:
    sandbox = root / "sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)
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
        managed_directories=[
            ManagedDirectory(name="sandbox", path=str(sandbox), read_only=read_only)
        ],
    )


# ---------------------------------------------------------------------------
# classify()
# ---------------------------------------------------------------------------


class TestClassify:
    def test_inside_cwd_preauthorized(self, tmp_path: Path):
        ctx = make_context(tmp_path)
        assert isinstance(classify(ctx, tmp_path / "f.txt", AccessMode.READ), PreAuthorized)
        assert isinstance(
            classify(ctx, tmp_path / "f.txt", AccessMode.WRITE), PreAuthorized
        )

    def test_outside_cwd_needs_confirmation_when_interactive(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        work = tmp_path / "work"
        work.mkdir()
        ctx = make_context(work, is_interactive=True)
        assert isinstance(classify(ctx, outside, AccessMode.READ), NeedsConfirmation)

    def test_outside_cwd_denied_when_not_interactive(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        work = tmp_path / "work"
        work.mkdir()
        ctx = make_context(work, is_interactive=False)
        grant = classify(ctx, outside, AccessMode.READ)
        assert isinstance(grant, Denied)
        assert "Permission denied" in grant.reason and "interactive" in grant.reason

    def test_cwd_none_denies_plain_paths(self, tmp_path: Path):
        ctx = make_context(None)
        grant = classify(ctx, tmp_path / "f.txt", AccessMode.READ)
        assert isinstance(grant, Denied)
        assert "disabled" in grant.reason

    def test_bond_and_git_read_allowed_write_denied(self, tmp_path: Path):
        ctx = make_context(tmp_path)
        for d in (".bond", ".git"):
            path = tmp_path / d / "x"
            assert isinstance(classify(ctx, path, AccessMode.READ), PreAuthorized)
            grant = classify(ctx, path, AccessMode.WRITE)
            assert isinstance(grant, Denied)
            assert f"`{d}`" in grant.reason and "read-only" in grant.reason

    def test_managed_dir_preauthorized_even_with_cwd_none(self, tmp_path: Path):
        persona = make_persona(tmp_path)
        ctx = make_context(None, persona=persona)
        sandbox_file = tmp_path / "sandbox" / "f.txt"
        assert isinstance(
            classify(ctx, sandbox_file, AccessMode.READ), PreAuthorized
        )
        assert isinstance(
            classify(ctx, sandbox_file, AccessMode.WRITE), PreAuthorized
        )

    def test_read_only_managed_dir_denies_write_only(self, tmp_path: Path):
        persona = make_persona(tmp_path, read_only=True)
        ctx = make_context(tmp_path, persona=persona)
        sandbox_file = tmp_path / "sandbox" / "f.txt"
        assert isinstance(
            classify(ctx, sandbox_file, AccessMode.READ), PreAuthorized
        )
        grant = classify(ctx, sandbox_file, AccessMode.WRITE)
        assert isinstance(grant, Denied)
        assert "read-only" in grant.reason and "sandbox" in grant.reason

    def test_bond_inside_managed_dir_still_write_denied(self, tmp_path: Path):
        persona = make_persona(tmp_path)
        ctx = make_context(None, persona=persona)
        bond_in_sandbox = tmp_path / "sandbox" / ".bond" / "x"
        grant = classify(ctx, bond_in_sandbox, AccessMode.WRITE)
        assert isinstance(grant, Denied)
        assert "`.bond`" in grant.reason


class TestPathHelpers:
    def test_path_is_in_git(self):
        assert path_is_in_git(Path("/x/.git/y"))
        assert path_is_in_git(Path(".git"))
        assert not path_is_in_git(Path("/x/git/y"))
        assert not path_is_in_git(Path("/x/.github/y"))

    def test_path_is_in_bond(self):
        assert path_is_in_bond(Path("/x/.bond/y"))
        assert path_is_in_bond(Path("a/.bond/b"))
        assert not path_is_in_bond(Path("/x/bond/y"))
        assert not path_is_in_bond(Path("/x/.bondx/y"))


# ---------------------------------------------------------------------------
# request_fs_access()
# ---------------------------------------------------------------------------


class TestRequestFsAccess:
    def test_inside_cwd_grants_without_prompt(self, tmp_path: Path):
        prompts: list[str] = []
        ctx = make_context(tmp_path, is_interactive=True, prompts=prompts)
        res = request_fs_access(ctx, "f.txt", AccessMode.READ)
        assert isinstance(res, Success)
        assert res.unwrap().path == tmp_path / "f.txt"
        assert res.unwrap().is_root
        assert prompts == []

    def test_outside_cwd_prompts_and_grants(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        work = tmp_path / "work"
        work.mkdir()
        prompts: list[str] = []
        ctx = make_context(work, is_interactive=True, confirm=True, prompts=prompts)
        res = request_fs_access(ctx, str(outside), AccessMode.READ)
        assert isinstance(res, Success)
        assert len(prompts) == 1
        assert "outside of the current working directory" in prompts[0]

    def test_outside_cwd_declined(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        work = tmp_path / "work"
        work.mkdir()
        ctx = make_context(work, is_interactive=True, confirm=False)
        res = request_fs_access(ctx, str(outside), AccessMode.READ)
        assert isinstance(res, Failure)
        assert "declined" in res.failure()

    def test_recursive_prompt_mentions_recursion(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        work = tmp_path / "work"
        work.mkdir()
        prompts: list[str] = []
        ctx = make_context(work, is_interactive=True, prompts=prompts)
        res = request_fs_access(ctx, str(outside), AccessMode.READ, recursive=True)
        assert isinstance(res, Success)
        assert res.unwrap().recursive
        assert "recursive" in prompts[0]

    def test_denied_recursive_request_is_not_downgraded(self, tmp_path: Path):
        """A declined recursive request fails as a whole — no silent non-recursive grant."""
        outside = tmp_path / "outside"
        outside.mkdir()
        work = tmp_path / "work"
        work.mkdir()
        ctx = make_context(work, is_interactive=True, confirm=False)
        res = request_fs_access(ctx, str(outside), AccessMode.READ, recursive=True)
        assert isinstance(res, Failure)
        assert "declined" in res.failure()

    def test_purpose_is_relayed_in_prompt(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        work = tmp_path / "work"
        work.mkdir()
        prompts: list[str] = []
        ctx = make_context(work, is_interactive=True, prompts=prompts)
        purpose = "Bond wants to patch the file x with this block:\n<<<<<<< SEARCH"
        res = request_fs_access(ctx, str(outside / "f.txt"), AccessMode.WRITE, purpose=purpose)
        assert isinstance(res, Success)
        assert purpose in prompts[0]

    def test_cwd_none_relative_path_disabled(self, tmp_path: Path):
        ctx = make_context(None)
        res = request_fs_access(ctx, "f.txt", AccessMode.READ)
        assert isinstance(res, Failure)
        assert "disabled" in res.failure()

    def test_cwd_none_bond_uri_still_works(self, tmp_path: Path):
        persona = make_persona(tmp_path)
        ctx = make_context(None, persona=persona)
        res = request_fs_access(ctx, "bond://sandbox/f.txt", AccessMode.READ)
        assert isinstance(res, Success)
        assert res.unwrap().path == tmp_path / "sandbox" / "f.txt"

    def test_unknown_bond_uri(self, tmp_path: Path):
        persona = make_persona(tmp_path)
        ctx = make_context(tmp_path, persona=persona)
        res = request_fs_access(ctx, "bond://nope/x", AccessMode.READ)
        assert isinstance(res, Failure)
        assert res.failure().startswith("Error:")
        assert "Unknown managed directory 'nope'" in res.failure()

    def test_bond_uri_escape_rejected(self, tmp_path: Path):
        persona = make_persona(tmp_path)
        ctx = make_context(tmp_path, persona=persona)
        res = request_fs_access(ctx, "bond://sandbox/../other", AccessMode.READ)
        assert isinstance(res, Failure)
        assert "escapes managed directory" in res.failure()

    def test_write_grant_to_bond_denied_without_prompt(self, tmp_path: Path):
        prompts: list[str] = []
        ctx = make_context(tmp_path, is_interactive=True, prompts=prompts)
        res = request_fs_access(ctx, str(tmp_path / ".bond" / "x"), AccessMode.WRITE)
        assert isinstance(res, Failure)
        assert "`.bond`" in res.failure()
        assert prompts == []  # hard denial, no prompt

    def test_write_grant_to_read_only_managed_denied(self, tmp_path: Path):
        persona = make_persona(tmp_path, read_only=True)
        ctx = make_context(tmp_path, persona=persona)
        res = request_fs_access(ctx, "bond://sandbox/x", AccessMode.WRITE)
        assert isinstance(res, Failure)
        assert "read-only" in res.failure()


# ---------------------------------------------------------------------------
# AuthorizedPath wrapper semantics
# ---------------------------------------------------------------------------


class TestAuthorizedPath:
    def test_write_grant_allows_read_on_same_path(self, tmp_path: Path):
        """apply_patch reads and writes a file under a single WRITE grant."""
        f = tmp_path / "f.txt"
        f.write_text("hello\n", encoding="utf-8")
        ctx = make_context(tmp_path)
        res = request_fs_access(ctx, "f.txt", AccessMode.WRITE)
        authorized = res.unwrap()
        assert authorized.read_text().unwrap() == "hello\n"

    def test_read_grant_denies_write(self, tmp_path: Path):
        f = tmp_path / "f.txt"
        f.write_text("hello\n", encoding="utf-8")
        ctx = make_context(tmp_path)
        authorized = request_fs_access(ctx, "f.txt", AccessMode.READ).unwrap()
        write_res = authorized.write_text("new")
        assert isinstance(write_res, Failure)
        assert "write access" in write_res.failure()
        assert f.read_text(encoding="utf-8") == "hello\n"

    def test_read_text_on_directory_fails(self, tmp_path: Path):
        ctx = make_context(tmp_path)
        authorized = request_fs_access(ctx, ".", AccessMode.READ).unwrap()
        res = authorized.read_text()
        assert isinstance(res, Failure)
        assert "not a file" in res.failure()

    def test_read_text_on_missing_file_fails(self, tmp_path: Path):
        ctx = make_context(tmp_path)
        authorized = request_fs_access(ctx, "nope.txt", AccessMode.READ).unwrap()
        assert isinstance(authorized.read_text(), Failure)

    def test_iterdir_on_file_fails(self, tmp_path: Path):
        f = tmp_path / "f.txt"
        f.write_text("x")
        ctx = make_context(tmp_path)
        authorized = request_fs_access(ctx, "f.txt", AccessMode.READ).unwrap()
        res = authorized.iterdir()
        assert isinstance(res, Failure)
        assert "not a directory" in res.failure()

    def test_recursive_grant_covers_subtree(self, tmp_path: Path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "deep.txt").write_text("deep", encoding="utf-8")
        ctx = make_context(tmp_path)
        root = request_fs_access(ctx, ".", AccessMode.READ, recursive=True).unwrap()
        children = root.iterdir().unwrap()
        sub = next(c for c in children if c.path.name == "sub")
        # derived children inherit the recursive grant: iterdir + read work
        grandchildren = sub.iterdir().unwrap()
        deep = next(c for c in grandchildren if c.path.name == "deep.txt")
        assert deep.read_text().unwrap() == "deep"

    def test_non_recursive_children_are_metadata_only(self, tmp_path: Path):
        (tmp_path / "f.txt").write_text("content", encoding="utf-8")
        ctx = make_context(tmp_path)
        root = request_fs_access(ctx, ".", AccessMode.READ, recursive=False).unwrap()
        children = root.iterdir().unwrap()  # listing the granted dir itself is fine
        f = next(c for c in children if c.path.name == "f.txt")
        # metadata is available...
        assert f.is_file()
        # ...but content reads on a non-root child require a recursive grant
        read_res = f.read_text()
        assert isinstance(read_res, Failure)
        assert "not recursive" in read_res.failure()

    def test_child_escape_refused(self, tmp_path: Path):
        ctx = make_context(tmp_path)
        root = request_fs_access(ctx, ".", AccessMode.READ, recursive=True).unwrap()
        res = root.child("../outside")
        assert isinstance(res, Failure)
        assert "escapes" in res.failure()

    def test_unlink(self, tmp_path: Path):
        f = tmp_path / "f.txt"
        f.write_text("x")
        ctx = make_context(tmp_path)
        authorized = request_fs_access(ctx, "f.txt", AccessMode.WRITE).unwrap()
        assert isinstance(authorized.unlink(), Success)
        assert not f.exists()

    def test_write_text_creates_parent_dirs(self, tmp_path: Path):
        ctx = make_context(tmp_path)
        authorized = request_fs_access(ctx, "a/b/c.txt", AccessMode.WRITE).unwrap()
        assert isinstance(authorized.write_text("hi"), Success)
        assert (tmp_path / "a" / "b" / "c.txt").read_text(encoding="utf-8") == "hi"

    def test_metadata_methods_ungated(self, tmp_path: Path):
        f = tmp_path / "f.txt"
        f.write_text("x")
        ctx = make_context(tmp_path)
        authorized = request_fs_access(ctx, "f.txt", AccessMode.READ).unwrap()
        assert authorized.exists()
        assert authorized.is_file()
        assert not authorized.is_dir()
        assert not authorized.is_symlink()
        assert isinstance(authorized.stat(), Success)


# ---------------------------------------------------------------------------
# ToolCallContext property hooks (extension point for a future grant cache)
# ---------------------------------------------------------------------------


class TestContextPropertyHooks:
    def test_hook_fires_only_on_actual_change(self, tmp_path: Path, monkeypatch):
        ctx = make_context(tmp_path)
        calls: list[None] = []
        monkeypatch.setattr(
            ctx, "_on_fs_access_policy_change", lambda: calls.append(None)
        )
        ctx.cwd = tmp_path  # same value -> no invalidation
        assert calls == []
        ctx.cwd = tmp_path / "other"  # changed -> invalidation
        assert len(calls) == 1
        ctx.persona = None  # unchanged (already None) -> nothing
        assert len(calls) == 1
        ctx.persona = make_persona(tmp_path)  # changed -> invalidation
        assert len(calls) == 2

    def test_request_fs_access_delegates(self, tmp_path: Path):
        ctx = make_context(tmp_path)
        res = ctx.request_fs_access("f.txt", AccessMode.READ)
        assert isinstance(res, Success)
        assert isinstance(res.unwrap(), AuthorizedPath)
