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

## Packages with extensive tests

- conversation

## Future Features

- Actual Skills and not just prompt macros
  - Definable skill-sets for a persona
  - Per Conversation enabled skills based on the persona
  - Popup for searching and enabling skills

Implementation Details:

- The conversation gets a new optional field called active_skills
- If this is None, then the available skills are exactly what the persona has as default
- If it is not None, then the skills are only those from this list
- On a persona switch, this list is left untouched.
- If the popup is used to change the available skills, then this new field is set according
  to the selected skills
- There is a reset button, which sets the value to None, tracking the ones form the persona again
- There is a clear button, which disables all skills by setting the value to an empty list
- There is a select-all button, which selects all filtered skills
- Maybe clear and select-all can be merged into a single button, but not clear yet

## Free Form Memory

- Memory storages with an id
- A persona can be granted access (read and/or write) to an FFM storage
- Inside, there is a directory structure and a index.md file, which describes the directory structure and roughly what is stored where
- Tools for reading and writing files (can reuse existing file tools)
- Profits from search tools like grep
- Maybe FFM can get indexed into a semantic vector store later on
