# Tools Module Summary

## Overview
The `src/bond/tools` module provides tool definitions, management, and various tool implementations for the chatbot system. Tools enable the AI to interact with external systems like filesystems, web services, and shell commands.

## Core Components

### 1. Tool Definitions (`tool.py`)
Defines the fundamental tool interface and related components:

- **ToolFn**: Type alias for tool functions (Callable that returns string, list, or dict)
- **FunctionParameter/FunctionParameters**: Define tool parameter schemas
- **Function**: Describes a tool's interface (name, description, parameters)
- **Tool**: Wraps a function with type information (`type: "function"`)

Key classes:
- **Toolbox**: Manages collections of tools
  - `call_tool()`: Execute a tool with arguments
  - `get_tool_descriptions()`: Get tool schemas for providers
  
- **ToolEnvironment**: Protocol defining the environment tools run in
  - Methods for interaction, confirmation, and output handling
  
- **activate_environment()**: Context manager for setting the active tool environment

### 2. Global Toolbox (`global_toolbox.py`)
Provides predefined toolsets:

- **Toolset Groups**:
  - `web-tools`: Web search and access tools
  - `fs-tools`: Filesystem operations
  - `shell`: Command execution
  - `write`: Output writing

- **get_toolsets()**: Selects and returns requested toolsets

### 3. Filesystem Tools (`fs_tools.py`)
Implements filesystem operations:

- **create_file()**: Create new files with content
- **read_file()**: Read file contents (with line limit option)
- **list_directory()**: List directory contents

All tools include:
- Path validation against working directory
- Interactive permission requests for external paths
- Error handling and user feedback

### 4. Shell Tools (`shell.py`)
Provides shell command execution:

- **run_shell_commands()**: Execute shell commands
- **allow_shell_commands()**: Context manager for enabling shell access

Features:
- User confirmation before execution
- Output logging to environment streams
- Safety checks (interactive mode required)

### 5. Web Tools

#### Web Search (`web_search.py`)
- **search_the_web()**: Perform web searches using DuckDuckGo
- Returns structured results with title, link, and snippet

#### Web Access (`web_access.py`)
- **access_web()**: Fetch and parse webpage content
- Respects robots.txt restrictions
- Uses BeautifulSoup for HTML parsing
- Implements retry logic and delays

#### Stream Tools (`stream_tools.py`)
- **write_to_output()**: Write data to output stream
- Used for streaming responses and tool output

## Important Utilities

- **Environment Management**:
  - `get_tool_environment()`: Get current tool environment
  - `activate_environment()`: Set active tool environment
  
- **Tool Execution**:
  - `Toolbox.call_tool()`: Execute tools with error handling
  - Result wrapping in `Success/Failure` types

## Integration Points

Other modules interact with tools through:
1. **Tool Definitions**: For creating and managing tools
2. **Toolbox**: For tool execution and schema generation
3. **Tool Environments**: For providing execution context
4. **Provider Integration**: Tools are parsed and called through provider interfaces

## Location Reference
All tool implementations are in `src/bond/tools/` with:
- Core definitions in `tool.py`
- Predefined toolsets in `global_toolbox.py`
- Filesystem tools in `fs_tools.py`
- Shell tools in `shell.py`
- Web tools in `web_search.py`, `web_access.py`, and `stream_tools.py`