# CLI Module Summary

## Overview
The `src/bond/cli` module contains the command-line interface entry points for the Bond chatbot system. These scripts provide the main user-facing interfaces for interacting with Bond through the command line.

## Core Components

### 1. CLI Entry Points
The module contains three main CLI entry points:

- **ask.py**: Single-turn question answering
- **chat.py**: Continuous chat conversation
- **followup.py**: Continue a previous single-turn interaction

### 2. Common Functionality
All CLI scripts share similar initialization patterns:

- **Configuration Loading**:
  - Loads configuration from `~/.config/bond/config.json`
  - Uses `BondConfig` for system-wide settings
  - Determines default persona from configuration

- **Environment Setup**:
  - Creates `DynamicBondEnvironment` from configuration
  - Sets up standard I/O tool environment
  - Configures standard agent output environment

- **Tool Integration**:
  - Loads toolsets based on configuration
  - Builds toolbox from persona configuration
  - Enables shell execution when in toolbox

### 3. ask.py - Single-Turn Question Answering

**Purpose**: Quick single-turn interactions with Bond

**Key Features**:
- Takes user input as command-line arguments
- Supports optional second argument for persona specification
- Configurable streaming output
- Automatic saving of conversation history
- Non-interactive mode support
- Input/output file options

**Usage**:
```bash
bond-ask "What is the meaning of life?"
bond-ask "What is the meaning of life? default-persona"
```

### 4. chat.py - Continuous Chat Conversation

**Purpose**: Interactive chat sessions with Bond

**Key Features**:
- Loads previous conversation if available
- Continuous interaction loop
- Command interface for conversation management
- Shell command execution support
- Automatic saving of conversation state
- Stream-based output

**Usage**:
```bash
bond-chat
```

### 5. followup.py - Continue Previous Interaction

**Purpose**: Continue a previous single-turn interaction

**Key Features**:
- Loads previous conversation from `last-ask.json`
- Creates new conversation if none exists
- Same interactive interface as chat
- Command management support
- Stream-based output

**Usage**:
```bash
bond-followup
```

## Integration Points

The CLI modules integrate with:
1. **Behaviours**: Using `SingleTurn` for ask mode and `LoopBehaviour` for chat
2. **Environment**: Using `DynamicBondEnvironment` for component access
3. **I/O**: Using standard I/O implementations for user interaction
4. **Configuration**: Using `BondConfig` for system settings
5. **Tools**: Using toolbox and tool environments for functionality

## Location Reference
All CLI entry points are in `src/bond/cli/` with:
- `ask.py`: Single-turn question answering
- `chat.py`: Continuous chat conversation
- `followup.py`: Continue previous interaction

## Common Patterns

1. **Environment Setup**:
   ```python
env = DynamicBondEnvironment(env_path, toolsets)
tool_environment = StdIoToolEnvironment(...)
aoe = StdAoe()
   ```

2. **Persona Selection**:
   ```python
persona_name = get_default_persona(config.chat)
persona = env.get_persona(persona_name)
provider = env.get_provider(persona.provider)
   ```

3. **Conversation Management**:
   ```python
conversation = Conversation()
conversation.add_message(ConversationMessage.create_user_message(...))
   ```

4. **Behavior Execution**:
   ```python
loop = LoopBehaviour(...)
loop.run()
   ```