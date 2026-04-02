# Base Bond Package Summary

## Overview
The `src/bond` package contains core functionality and interfaces that form the foundation of the Bond chatbot system. These files provide essential utilities, configuration handling, environment management, and persona definitions.

## Core Components

### 1. Utilities (`util.py`)
Provides essential utility functions for the system:

- **HTTP Handling**:
  - `http_retry_loop()`: Robust HTTP request handling with retry logic
  - Handles common HTTP error codes (408, 429, 500-504)
  - Implements exponential backoff for retries
  - Logs detailed error information

- **API Key Management**:
  - `resolve_api_key()`: Resolves API keys from environment variables or raw values
  - Supports `ENV:` prefix for environment variable references

- **Stream Processing**:
  - `parse_sse_stream()`: Parses Server-Sent Events (SSE) streams
  - Converts stream data into usable events

### 2. Configuration (`config.py`)
Defines configuration structures for the Bond system:

- **AskConfig/ChatConfig**: Configuration for ask/chat modes
  - `personas`: List of allowed personas
  - `default_persona`: Default persona to use
  - `tools`: List of available toolsets

- **BondConfig**: Main configuration class
  - Combines ask and chat configurations
  - Includes `user_name` setting
  - Provides `load_from()` classmethod for loading from JSON files

- **get_default_persona()**: Helper function to determine default persona

### 3. Persona Definitions (`persona.py`)
Defines the persona system:

- **Persona**: Represents an AI persona configuration
  - `name`: Persona identifier
  - `model`: Model to use
  - `provider`: Provider to use
  - `system_prompt`: Optional system prompt
  - `toolbox`: List of toolsets to use
  - `model_options`: Provider-specific model options

- **Loading**:
  - `load_from()` classmethod for loading personas from JSON files

### 4. Bond Environment (`bond_environment.py`)
Defines the environment interface and implementations:

- **BondEnvironment (Protocol)**:
  - Defines the interface for environment access:
    - `list_toolsets()`: Get available toolsets
    - `list_personas()`: Get available personas
    - `list_providers()`: Get available providers
    - `get_toolset()`: Get specific toolset
    - `get_persona()`: Get specific persona
    - `get_provider()`: Get specific provider

- **StaticBondEnvironment**:
  - Pre-configured environment with all components
  - Direct access to providers, personas, and tools
  - No dynamic loading

- **DynamicBondEnvironment**:
  - Environment that loads components from filesystem
  - Supports discovery of personas and providers
  - Caching of loaded components
  - Methods for clearing cache and reloading

### 5. Command Handling (`default_command_handler.py`)
Implements the default command handler for interactive sessions:

- **DefaultCommandHandler**:
  - Handles user commands in interactive mode
  - Provides commands for conversation management:
    - `quit/save/load/new/help/forget/remember/export`
    - `length/last/crop/who/to/delete`
  - Shell command integration (prefix with ':')
  - Conversation persistence
  - Persona switching

- **Command Integration**:
  - Argument parser with subcommands
  - Callback-based command execution
  - Error handling and user feedback

## Important Utilities

- **Configuration Management**:
  - Type-safe configuration with Pydantic models
  - JSON serialization/deserialization
  - Default value handling

- **Environment Abstraction**:
  - Protocol-based interface for environments
  - Static vs dynamic implementations
  - Component discovery and loading

- **HTTP and Stream Handling**:
  - Robust HTTP requests with retry logic
  - SSE stream parsing
  - API key resolution

## Integration Points

Other modules interact with the base package through:
1. **Utilities**: For HTTP, stream processing, and API key handling
2. **Configuration**: For system-wide settings
3. **Personas**: For AI persona definitions
4. **Environments**: For component access and management
5. **Command Handling**: For interactive user sessions

## Location Reference
Core base functionality is defined in `src/bond/` with:
- Utilities in `util.py`
- Configuration in `config.py`
- Personas in `persona.py`
- Environment in `bond_environment.py`
- Command handling in `default_command_handler.py`