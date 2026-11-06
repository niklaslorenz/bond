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

## Packages with extensive tests

- conversation

## Future Features

- Skill directories with `tools/*.py` (`EXPORT_TOOLS`) -> `PythonToolset("skill:<name>")`,
  plus live toolbox enable/disable and skill-sync on persona switch
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
- The old prompt macros are now "prompts" (`{PROMPT:name}`)

## Free Form Memory

- Memory storages with an id
- A persona can be granted access (read and/or write) to an FFM storage
- Inside, there is a directory structure and a index.md file, which describes the directory structure and roughly what is stored where
- Tools for reading and writing files (can reuse existing file tools)
- Profits from search tools like grep
- Maybe FFM can get indexed into a semantic vector store later on
