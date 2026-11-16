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
- Managed directories (`managed_directories`): always-accessible folders addressed
  via `bond://<name>/<path>` URIs, optionally read-only — see
  [Managed Directories](./docs/personas/managed-directories.md)

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

## Future Features

- `requirements.txt` per skill for dependency installation
- Status bar segment showing the conversation's active skills

### Keymap help page

- A unified way to define keymap schemes that can be used for different contexts inside the tui
- A help popup that shows a key and description table
