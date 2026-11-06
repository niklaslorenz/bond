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

## Prompts vs. skills

The old prompt macros live on as **prompts**: markdown files in
`~/.config/bond/prompts/*.md` that are substituted into any prompt string via
the `{PROMPT:name}` macro (resolved at load time, e.g. in `system_prompt`).
Use prompts for static text snippets; use skills for agent-activatable
instruction packages with metadata.
