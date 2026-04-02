# Endpoints Module Summary

## Overview
The `src/bond/endpoints` module contains endpoint handlers and models for the chatbot system, following a protocol-oriented design.

## Key Classes/Interfaces

### 1. ModelOptions (`model_options.py`)
- **Purpose**: Base class for model configuration options
- **Important Methods**:
  - `parse()`: Converts options to dictionary
- **Usage**: Extended by specific model option classes

### 2. ModelCapabilities (`models.py`)
- **Purpose**: Defines capabilities supported by models
- **Fields**: Audio, vision, function calling, etc.
- **Usage**: Used in model definitions to specify capabilities

### 3. BaseModelCard (`models.py`)
- **Purpose**: Base model information structure
- **Fields**: ID, name, capabilities, creation date, etc.
- **Usage**: Represents model metadata

### 4. ModelsEndpoint (`models.py`)
- **Purpose**: Protocol defining model retrieval interface
- **Important Methods**:
  - `retrieve_model(id: str)`: Get specific model
  - `list_models()`: List all available models
- **Usage**: Core interface for model management

### 5. ChatCompletionsEndpoint (`chat_completions.py`)
- **Purpose**: Protocol for chat completion operations
- **Important Methods**:
  - `chat_completion()`: Standard chat completion
  - `stream_chat_completion()`: Streaming chat completion
  - `supports_streaming()`: Check streaming support
- **Usage**: Primary interface for chat interactions

### 6. CompletionResponse/CompletionChunk (`chat_completions.py`)
- **Purpose**: Response models for chat completions
- **Fields**: Message content, usage info, etc.
- **Usage**: Returned by chat completion endpoints

## Important Utilities

- `merge_options()`: Merges multiple model option configurations
- `build_response()`: Constructs final response from streaming chunks

## Integration Points

Other modules will likely interact with:
1. `ModelsEndpoint` for model management
2. `ChatCompletionsEndpoint` for chat operations
3. Model option classes for configuration
4. Response models for handling results

## Location Reference
All definitions are in `src/bond/endpoints/` module files.