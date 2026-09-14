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
