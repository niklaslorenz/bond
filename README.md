# Bond

Bond is an agent framework for the terminal. It provides different methods to interact with an agent and can be configured to fit your needs.

## Personas

Personas are at the heart of bond. For every persona, you can define:

- Which model to use
- The system prompt
- The tools available to the agent
- The context summarization behaviour
- etc.

Personas are also part of the plugin system, so they can be even more customizable

## Providers

Providers are what gives you access to language models. You configure them with your access credentials
so bond can work with its models.

### Mistral

Bond is built upon Mistral's api data layouts and will probably work best
with this api.

The configuration for Mistral supports the following:

```json
{
  "type": "mistral"
  "api_key": "<your api key>"
}
```

The API key can be either the literal key or a link to an environment variable
that holds the key by prefixing it with "ENV:", for example:
`"api_key": "ENV:MISTRAL_API_KEY`.

### Ollama

Ollama's interface provides almost no information for a model via its api
and no information whatsoever about a models capabilities. Bond thus assumes
that a model has all possible capabilities and it is on the user to make sure
to select a model that indeed does support the needed functionalities.

The configuration for Ollama supports the following fields:

```json
{
  "type": "ollama",
  "base_url": String,
  "api_key": String or null,
  "models": List[String] or null,
  "chat_completion_options": OllamaChatCompletionOptions,
  "model_specific_chat_completion_options": Map[String, OllamaChatCompletionOptions] or null,
  "max_context_length": int or null
}
```

#### OllamaChatCompletionOptions

```json
{
  "frequency_penalty": float or null,
  "presence_penalty": float or null,
  "seed": int or null,
  "stop": String or List[String] or null,
  "stream": bool or null,
  "temperature": float or null,
  "top_p": float or null,
  "reasoning_effort": "high" or "medium" or "low" or "none"
}
```

The base_url must not point inside any endpoint, for a locally hosted environment
for example this would be `"base_url": "http://localhost:11434/"`

## TODO

### Summarization

- Add a way for the working set handler and task list handler to actually see what they have to edit!

### TUI

- Reintroduce chat log scrolling with ctrl + j/k
- (Prevent scrolling when new message is already on top)

## Known Issues

- Deleting messages can result a message list that is shorter than the amount of specified kept turns in the summary configuration

- Task List and Working Set are not used yet

- Saving a conversation as last conv and loading it leads to a broken state in the saved conversation because the cache
  is constructed from the last conv file and is unaware of the status of the actual conversation file
  => fix: let the last-conv be just the path and name of the last conversation (reference like) and store a temporary
  conversation in cache_path / temp and let the last conv point there. On a rename, move the conversation to
  the conversations dir and change the reference in last_conv

- Hit rate is off when loading a conversation

- Errors in command execution lead to a textual crash somehow

  ## Packages with extensive tests

  - conversation
