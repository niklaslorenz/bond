# Feature plan: apply_patch returns change context

## Overview

Today `apply_patch` only reports `Block N: success` / `Modified files: {...}`,
so the agent has to call `read_file` again to verify the patch landed at the
right position. This feature makes `apply_patch` return, for every successfully
applied block, the changed region of the file **with a few lines of context
before and after** (line-numbered, changed lines marked), so the agent can see
immediately whether the patch landed where intended.

## Open questions / decisions

- **How much context?** Decision: 3 lines before and after the changed region
  (constant `CONTEXT_LINES = 3` in `apply_patch.py`). Easy to tweak later.

- **What if the replaced region is huge?** Decision: cap the displayed snippet
  at 20 lines of the changed region, with a `... (N more changed lines)` note.
  Context lines are always fully shown.

- **Which blocks get a snippet?** Only successful blocks (exact and fuzzy
  matches alike). Failed blocks keep their current error lines unchanged.

- **Multiple blocks in one file**: snippets are computed against the file
  state *at the moment that block was applied* (blocks apply sequentially), so
  each snippet reflects the position in the evolving file.

- **Format** (per successful block):

  ```
  Block 0: success — src/bond/foo.py (changed lines 12-14)
     10:     context line
     11:     context line
  >  12:     new line 1
  >  13:     new line 2
  >  14:     new line 3
     15:     context line
     16:     context line
     17:     context line
  ```

  Changed lines are prefixed with `>`, context lines with line numbers only.
  The existing `Block N: success` prefix is kept (tests and the agent may rely
  on it) and extended with the file/line info; the final `Modified files:` line
  stays unchanged.

## Design decisions

- **Where**: all changes in `src/bond/tools/file_system/apply_patch.py`.
  A helper `_format_change_snippet(new_text: str, start_line: int, n_changed: int) -> list[str]`
  builds the snippet from the post-write file content. The two application
  paths (exact `str.replace` and fuzzy line-span) are refactored to compute
  `(start_line_index, n_changed_lines)` instead of only writing the file:
  - exact match: locate `search` in the current text, convert char offset to a
    0-based line index; `n_changed = len(replace.splitlines())`.
  - fuzzy match: the existing `span` gives `(start, end)` in original lines;
    `n_changed = len(replace.splitlines())`, snippet starts at `start`.
- **Why not a unified diff**: diffs require the original text and are harder
  to eyeball for "did it land at the right position"; a line-numbered snippet
  of the *result* matches how `read_file` output looks, so the agent can
  compare directly.
- **Tool description**: extended to say the result contains the changed
  region with context lines, so the agent knows it doesn't need to re-read.
- **No truncation concerns**: tool results are passed to the model verbatim;
  the 20-line cap on changed lines keeps snippets bounded.

## Task list

- [x] `src/bond/tools/file_system/apply_patch.py`: added `CONTEXT_LINES = 3` / `MAX_SNIPPET_CHANGED_LINES = 20` + `_format_change_snippet()`; exact-match path computes `start_line` via char offset, fuzzy path uses the span start; each successful block appends a header (`Block N: success — <file> (changed lines X-Y)` / `(deletion at line X)`) plus the line-numbered snippet with `>` markers; tool `description` updated.
- [x] Tests in new `test/bond/tools/test_apply_patch.py`: exact-match snippet with context + markers, multi-line range, deletion (no markers), fuzzy-match snippet, multi-block snippets, failed block (no snippet, file unchanged), large-replacement cap (`... (N more changed lines)` and trailing context shown).
- [ ] Run full test suite (user-run per workflow, e.g. via `.bond/scripts/run-tests.sh`); verify no regressions.
- [x] Docs: the `apply_patch` tool description documents the snippet behavior (that is the user-facing doc); no separate tools doc page exists.

## Progress / changes

- `src/bond/tools/file_system/apply_patch.py`: snippet helper + integration in both match paths + description. Snippet caps the *changed* region at 20 lines (with a `... (N more changed lines)` note, then jumps to the trailing context) and always shows up to 3 context lines before/after.
- `test/bond/tools/test_apply_patch.py`: new, 7 tests covering the cases above.
