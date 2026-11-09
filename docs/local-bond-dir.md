# Project-local configuration: the `.bond` directory

A `.bond` directory in your project extends bond with project-local skills,
scripts, and conversations:

```
.bond/
  skills/<name>/SKILL.md    # local skills, same format as global ones
  scripts/                  # scripts runnable via the `local` toolset
  conversations/            # local conversation store (lsave / lload)
```

## Discovery rule

When bond starts (and whenever it needs the local directory), it searches
**from the current working directory upwards** for the *closest* `.bond`
directory. If several parents up the tree have one, the nearest one wins and
the others are ignored — there is no merging.

Because discovery is based on the current working directory, it follows `:cd`
(and any other directory change) during a session: the tools always see the
`.bond` of the project you are currently in.

## Opting out: `--disable-local-config`

All entry points accept `--disable-local-config` (`talk`, `chat`, `ask`,
`followup`). With it, any `.bond` directory is ignored completely: no local
skills, no local scripts, and `lsave` / `lload` report that they need a
`.bond` directory.

## Local skills

Skills in `.bond/skills/` use the exact same format as global skills
(`~/.config/bond/skills/`, see [Skills](./skills.md)). A local skill
**shadows** a global skill of the same name — `get_skill` checks the local
directory first. Local skills are cached by their absolute path (not by
name), so switching between two projects that both define a skill called
`shared` resolves correctly. `bond skills` lists local skills together with
global ones.

To make **all** local skills available without listing them individually, set
`"use_local_skills": true` in the persona config — see
[Skills](./skills.md#use_local_skills-make-all-project-local-skills-available).
A conversation-level `available_skills` list still takes precedence.

## Local scripts: the `local` toolset

The builtin `local` toolset lets the agent discover and run the scripts your
project ships in `.bond/scripts/`:

- `list_local_scripts()` — lists the scripts with a one-line description taken
  from the first `# ...` comment (shebang skipped).
- `run_local_script(script_name, args?, timeout?)` — runs one of them.

Safety properties:

- Only **plain file names directly inside `.bond/scripts/`** are accepted —
  path separators, `..`, and symlinks resolving outside the directory are
  rejected.
- Execution always uses `subprocess` with `shell=False`; arguments are passed
  as-is and never shell-interpreted. `.py` files run with the current Python
  interpreter, `.sh` files with `sh`, executable files directly.
- Because `.bond/scripts/` is an explicit, user-controlled allowlist, scripts
  run **without a per-call confirmation**.
- The script runs with the **project root** (the directory containing `.bond`)
  as its working directory. Output is capped at the last 50 lines of
  stdout/stderr; `timeout` defaults to 60s.

## Local conversations: `lsave` / `lload`

- `:lsave <name>` saves the current conversation into `.bond/conversations/`
  (instead of the global store used by `:save`).
- `:lload <name>` loads a conversation from `.bond/conversations/`.

Both exist in the TUI and in the interactive CLI (`:`-commands), and both
require a `.bond` directory — otherwise they print an error instead of
falling back to the global store. `lsave` also requires a name (or an already
named conversation), same as `save`.

## Write protection

`.bond` and `.git` directories are **read-only for agent tools**: the write
tools (`create_file`, `apply_patch`, `remove_file`) refuse to write or delete
any path inside a `.bond` or `.git` folder (no matter which project is
currently active), while reading (`read_file`, …) stays allowed. `.bond` is
managed by you, `.git` by git — not by the agent.
