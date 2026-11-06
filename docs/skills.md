# Skills

Skills are reusable instruction packages that an agent can activate for a
conversation. Unlike [prompts](#prompts-vs.-skills), which are text macros
substituted into a prompt at load time, a skill is a directory with structured
metadata that the agent can discover, load, and unload *during* a conversation.

## Skill directory layout

Skills live in the bond config directory:

```
~/.config/bond/skills/<name>/SKILL.md
```

`<name>` is the skill's identifier — it is what the agent refers to when loading
the skill and what goes into the allow-lists (see below).

### SKILL.md format

A `SKILL.md` file starts with an optional frontmatter block delimited by `---`
lines. Only `name` and `description` are understood; everything after the
closing `---` is the skill's instructions:

```markdown
---
name: pdf-tools
description: Tools for extracting and analyzing PDFs.
---
# Instructions

When the user mentions PDFs, use the pdf tools to extract text and metadata.
Always summarize the document structure before the content.
```

- `name` is optional — if missing, the directory name is used.
- `description` is optional but strongly recommended: it is what the agent sees
  in the list of available skills when deciding which skill to load.
- The frontmatter is parsed manually (no YAML dependency), so keep it simple:
  one `key: value` per line, values may be quoted.

### Listing discovered skills from the CLI

`bond skills` lists every skill the runtime discovers in
`~/.config/bond/skills/` (directories containing a `SKILL.md`), with each
skill's description:

```
$ bond skills
Skills:
  pdf-tools: Tools for extracting and analyzing PDFs.
  git-helpers
```

## Activating skills: the `skills` toolset

Loading and unloading is done through two builtin tools, registered as the
`skills` toolset:

- `load_skill(name)` — verifies `name` against the conversation's *available*
  skills (denied requests return an error listing what is available), appends
  it to the conversation's active skills, and returns a short confirmation.
  The skill content itself is **not** put into the tool result; it appears in
  the `<active-skills>` system-prompt section instead, so it is not duplicated
  into the message history. Loading an already-active skill is idempotent.
- `unload_skill(name)` — removes the skill from the active skills.

For the agent to see these tools, the persona's `toolsets` must include
`"skills"`:

```json
{
  "name": "assistant",
  "generation": {
    "model": "mistral-large-latest",
    "system_prompt": "You are a helpful assistant."
  },
  "toolsets": ["file", "shell", "skills"],
  "available_skills": ["pdf-tools", "git-helpers"]
}
```

## Configuring available skills on a persona

The `available_skills` field of a persona config lists the skills that are
available by default for every conversation with that persona:

| Value                          | Meaning                            |
| ------------------------------ | ---------------------------------- |
| `["pdf-tools", "git-helpers"]` | exactly these skills are available |
| `[]` (or omitted)              | no skills available                |

```json
"available_skills": ["pdf-tools", "git-helpers"]
```

## Per-conversation override

Each conversation stores its own `available_skills` field (in its metadata
JSON) with tri-state semantics:

| Value        | Meaning                                                        |
| ------------ | -------------------------------------------------------------- |
| `null`       | inherit the persona's `available_skills` (this is the default) |
| `[]`         | explicitly no skills available for this conversation           |
| `["a", "b"]` | exactly these skills are available                             |

## Managing skills in the TUI: `:skills`

In the chat TUI, the `:skills` command (alias `:skill`) opens a popup to manage
the current conversation's skills (only while the agent is idle):

- One row per skill on disk, plus any skills referenced by the conversation
  that are missing on disk (shown as `(missing)`).
- Each row shows two states: **available** (`[x]` / `[ ]`) and **active**
  (`●` / `○`). A mode line on top shows whether `available_skills` is currently
  *inheriting from the persona* or a *custom* list.
- Keys (vim-style, two focus modes — the hint line at the bottom shows the
  current mode):
  - anywhere: `up`/`down` (or `ctrl+k`/`ctrl+j`) move the highlight,
    `enter` applies, `tab` switches between search and list, `ctrl+z` cancels.
  - search focused (default): type to filter rows (same fuzzy matching as the
    conversation selector); `esc`/`tab` switch to the list.
  - list focused: `j`/`k` move the highlight, `a` toggles **available**
    (unchecking an active skill also deactivates it), `s` toggles **active** —
    activating a skill that is not available yet also makes it available,
    while deactivating keeps it available, `q` cancels, `/` switches back to
    the search, `esc` cancels.
- Buttons: **All** / **None** apply to the currently filtered rows, **Clear**
  sets available to an explicit empty list, **Reset (persona)** goes back to
  inherit mode (`available_skills = null`), **Apply** commits, **Cancel**
  discards.
- Clicking a row toggles its available state; clicking the `●`/`○` toggle
  switches active (activating implies available, deactivating does not revoke
  availability).

Changes take effect on the next generation (the system message is re-rendered
every turn) and are persisted with the conversation metadata on save.

## Prompts vs. skills

The old prompt macros live on as **prompts**: markdown files in
`~/.config/bond/prompts/*.md` that are substituted into any prompt string via
the `{PROMPT:name}` macro (resolved at load time, e.g. in `system_prompt`).
Use prompts for static text snippets; use skills for agent-activatable
instruction packages with metadata.
