# Providers Module Summary

## Overview
The `src/bond/providers` module implements provider-specific implementations for different LLM providers (Mistral, Ollama, OpenAI) following a unified interface.

## Core Components

### 1. Provider Protocol (`provider.py`)
Defines the unified interface that all providers must implement:

```python
class Provider[ModelArgumentType: ModelOptions](Protocol):
    def models(self) -> ModelsEndpoint: ...
    def chat_completions(self) -> ChatCompletionsEndpoint[ModelArgumentType]: ...
    def parse_tool(self, tool: ToolFn) -> tuple[str, Tool]: ...
```

### 2. Provider Configurations
Base configuration classes for each provider:

- **OpenAIConfig**: Basic OpenAI configuration
- **OllamaConfig**: Configuration for Ollama provider with options for:
  - Base URL and API key
  - Model-specific options
  - Chat completion parameters
- **MistralConfig**: Configuration for Mistral provider with:
  - API key
  - Model whitelisting
  - Chat completion options

### 3. Provider Implementations

#### Ollama Provider
Implements the Ollama LLM provider:

- **Ollama**: Main provider class that:
  - Initializes models and chat completions endpoints
  - Provides `models()`, `chat_completions()`, and `parse_tool()` methods
  
- **OllamaModels**: Handles model operations:
  - `retrieve_model()`: Get specific model info
  - `list_models()`: List available models
  
- **OllamaChatCompletions**: Handles chat completions:
  - `chat_completion()`: Standard chat completion
  - `stream_chat_completion()`: Streaming chat (not implemented)
  - `supports_streaming()`: Returns False

#### Mistral Provider
Implements the Mistral LLM provider:

- **Mistral**: Main provider class that:
  - Initializes models and chat completions endpoints
  - Provides `models()`, `chat_completions()`, and `parse_tool()` methods
  - Includes `default()` classmethod for easy initialization
  
- **MistralModels**: Handles model operations:
  - `retrieve_model()`: Get specific model info
  - `list_models()`: List available models
  
- **MistralChatCompletions**: Handles chat completions:
  - `chat_completion()`: Standard chat completion
  - `stream_chat_completion()`: Streaming chat with callback support
  - `supports_streaming()`: Returns True

#### OpenAI Provider
Basic OpenAI provider implementation:

- **OpenAIConfig**: Configuration class for OpenAI

## Important Utilities

- `load_config_from()`: Loads provider configuration from JSON file
- `construct_provider()`: Factory function to create provider instances
- `build_toolbox()`: Creates toolbox from list of tools

## Integration Points

Other modules will interact with:
1. Provider protocol for unified interface
2. Provider implementations for specific LLM access
3. Configuration classes for provider setup
4. Models and chat completions endpoints for actual operations

## Location Reference
All provider implementations are in `src/bond/providers/` with provider-specific code in subdirectories (ollama/, mistral/) or individual files (openai.py).