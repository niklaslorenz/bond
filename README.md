# Bond

Bond is an agent framework for your terminal. It provides different entry points to interact with an agent and can be configured to fit your needs.

Customization includes:

- [Personas](#personas)
- [Providers](#providers)
- [Toolsets](#toolsets)
- [Skills](#skills)

## Personas

Personas are at the heart of bond. They describe the behaviour of the agent and what it can
and cannot do. For every persona, you can define:

- Which provider/model to use
- The system prompt
- The tools available to the agent
- The summarization behaviour

## Providers

Providers are what gives you access to language models. You configure them with your access
credentials so bond can work with its models.

Currently supported providers are:

- [Mistral](./docs/providers/mistral.md)
- [Ollama](./docs/providers/ollama.md)

## Skills

Skills are directory-based instruction packages (`~/.config/bond/skills/<name>/SKILL.md`)
that the agent can load and unload per conversation via the `load_skill` / `unload_skill`
tools. Available skills are configured per persona (`available_skills`) and can be
overridden per conversation. Run `bond skills` to list all discovered skills.
See [Skills](./docs/skills.md) for the full documentation.

Projects can extend bond with a local `.bond/` directory (project-local skills,
scripts, and conversations) — see
[Project-local configuration](./docs/local-bond-dir.md).

## Packages with extensive tests

- conversation

## TODOs

- **Rethink `AsyncAgentLoop` state ownership.** The loop currently holds
  `_persona`, `_persona_toolbox`, `_conversation`, ... and rebuilds them via
  `_build_turn()` whenever the persona/conversation changes (`set_persona`,
  `set_conversation`). This pattern hits its limits: every new piece of state
  has to be explicitly threaded through `_build_turn`, and the loop mutates the
  conversation (e.g. pruning `active_skills`) instead of deriving state from
  it. Better: work like the skill toolsets — before every turn, reconcile the
  held objects against `self._conversation` (e.g. `_check_skill_toolsets()`)
  instead of pushing changes into the conversation through the loop.

## Future Features

- `requirements.txt` per skill for dependency installation
- Status bar segment showing the conversation's active skills

Implemented (see [Skills](./docs/skills.md)):

- Directory-based skills with `SKILL.md` frontmatter (name / description / instructions)
- Definable skill-sets per persona (`available_skills` in the persona config)
- Per-conversation override (`available_skills`: `null` = inherit persona, `[]` = none,
  list = exactly these) and per-conversation `active_skills`
- `load_skill` / `unload_skill` tools (builtin `skills` toolset) with allow-list enforcement
- `<available-skills>` / `<active-skills>` sections in the system prompt, with the
  `active ⊆ available` invariant enforced (popup + builder filter)
- `:skills` popup in the TUI for managing available/active skills per conversation
  (search, bulk actions, reset-to-persona, materialize-on-first-toggle)
- Skill-provided tools: `skills/<name>/tools/*.py` exporting `EXPORT_TOOLSETS`,
  lazily imported and exposed with the `sk:<name>:` prefix while the skill is
  active (see `feature_plan_skill_tools.md`)
- The old prompt macros are now "prompts" (`{PROMPT:name}`)

### Free Form Memory

- Memory storages with an id
- A persona can be granted access (read and/or write) to an FFM storage
- Inside, there is a directory structure and a index.md file, which describes the directory structure and roughly what is stored where
- Tools for reading and writing files (can reuse existing file tools)
- Profits from search tools like grep
- Maybe FFM can get indexed into a semantic vector store later on

### Keymap help page

- A unified way to define keymap schemes that can be used for different contexts inside the tui
- A help popup that shows a key and description table
