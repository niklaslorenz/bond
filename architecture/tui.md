# TUI Module Summary

## Overview
The `src/bond/tui` module implements a Text User Interface (TUI) for the Bond chatbot system using the Textual framework. This provides a rich, interactive terminal-based interface for interacting with Bond.

## Core Components

### 1. Main Application (`app.py`)
The core TUI application that extends Textual's `App` class:

- **BondTui**: Main application class
  - Manages the complete TUI lifecycle
  - Handles message display and user interaction
  - Coordinates between signal and event queues
  - Manages conversation state and widgets

**Key Features**:
- Real-time chat log display
- Status bar showing persona, provider, and context
- Input handling with multi-line support
- Message synchronization with conversation history
- Event-driven architecture using queues

### 2. Widgets (`widgets.py`)
Custom Textual widgets for the chat interface:

- **StatusBar**: Reactive status display
  - Shows current persona, provider, status, and context length
  - Updates automatically as state changes

- **InputBar**: Multi-line text input
  - Supports Shift+Enter for new lines
  - Enter submits the message
  - Command mode (prefix with ':')

- **ChatMessage**: Message display component
  - Handles user, assistant, system, and tool messages
  - Supports text, thinking, and tool result blocks
  - Automatic folding for long content

- **ChatLog**: Scrollable message container
  - Manages the complete message history
  - Automatic scrolling to new messages
  - Message synchronization

**Special Widgets**:
- **TextBlock**: Basic text display
- **ThinkBlock**: Foldable thinking content
- **ToolResultBlock**: Foldable tool results
- **MultiLineInput**: Enhanced text input with multi-line support

### 3. Command Handler (`command_handler.py`)
TUI-specific command handler that extends the default CLI handler:

- **TuiCommandHandler**: TUI-aware command processor
  - Extends `DefaultCommandHandler` with TUI-specific features
  - Manages event queue for UI updates
  - Synchronizes UI state with command execution

**Key Features**:
- UI blocking during operations
- Automatic UI updates after commands
- Persona switching with UI updates
- Conversation synchronization

### 4. Main Entry Point (`main.py`)
The main entry point that sets up and runs the TUI:

- **Main Function**:
  - Sets up signal and event queues
  - Initializes environment and configuration
  - Creates conversation and tool environment
  - Sets up command handler and behavior loop
  - Launches TUI application in separate thread

**Integration**:
- Bridges between CLI-style initialization and TUI operation
- Sets up the complete TUI environment
- Manages threading between behavior loop and TUI

## Important Utilities

- **Event System**:
  - Signal queue for user input
  - Event queue for UI updates
  - Automatic synchronization between components

- **Message Handling**:
  - Real-time message display
  - Thinking content folding
  - Tool result organization
  - Automatic scrolling

- **State Management**:
  - Reactive UI updates
  - Context length tracking
  - Persona and provider display

## Integration Points

The TUI integrates with:
1. **Behaviours**: Using `LoopBehaviour` for conversation management
2. **Environment**: Using `DynamicBondEnvironment` for component access
3. **I/O**: Using queue-based implementations for async communication
4. **Signals**: For user input handling
5. **Events**: For UI updates and synchronization

## Interaction Flow

1. **Initialization**:
   - Environment and configuration setup
   - Widget creation and layout
   - Queue setup for communication

2. **User Input**:
   - Multi-line input handling
   - Command parsing (prefix with ':')
   - Signal generation and queueing

3. **AI Processing**:
   - Behavior loop processes signals
   - Results sent to event queue
   - UI updates automatically

4. **Display**:
   - Real-time message rendering
   - Status updates
   - Automatic scrolling

5. **Command Execution**:
   - Command handler processes commands
   - UI state synchronized
   - Event-driven updates

## Location Reference
All TUI components are in `src/bond/tui/` with:
- Main application in `app.py`
- Widgets in `widgets.py`
- Command handler in `command_handler.py`
- Main entry point in `main.py`
- CSS styling in `tui.css`

## Current Status
The TUI module is marked as needing polish, likely including:
- Better error handling and user feedback
- More sophisticated message organization
- Enhanced styling and theming
- Additional interactive features
- Improved performance with large conversations
- Better tool integration display