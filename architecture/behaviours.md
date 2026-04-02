# Behaviours Module Summary

## Overview
The `src/bond/behaviours` module implements the core interaction patterns and behavior loops for the Bond chatbot system. It handles how the system processes user input, manages conversations, and executes AI responses.

## Core Components

### 1. Behaviour Signals (`behaviour_signal.py`)
Defines the signal types used for inter-process communication:

- **StopSignal**: Signal to stop the current behavior
- **PromptSignal**: Signal containing user input/prompt
- **CommandSignal**: Signal containing a command to execute

- **BehaviourSignal**: Union type of all signal types
- **SignalAdapter**: Type adapter for parsing behavior signals

These signals enable clean separation between input handling and behavior execution.

### 2. Single Turn Behaviour (`single_turn.py`)
Implements a single conversation turn with an AI model:

- **SingleTurn**: Main class for handling one complete interaction
  - Takes a conversation and produces a response
  - Handles both streaming and non-streaming responses
  
- **Key Features**:
  - System message handling
  - Tool integration and execution
  - Shell command execution (when allowed)
  - Response streaming to output environment
  
- **Tool Execution**:
  - Calls tools based on model responses
  - Handles tool results and error cases
  - Manages tool environment activation
  - Supports shell command execution with safety checks

### 3. Loop Behaviour (`loop.py`)
Implements the main interaction loop for continuous conversation:

- **LoopBehaviour**: Main class for managing ongoing conversations
  - Maintains conversation state
  - Handles persona switching
  - Manages signal processing loop
  - Coordinates between input, AI processing, and output

- **Key Features**:
  - Continuous operation until stop signal
  - Persona management and switching
  - Command handling integration
  - Tool environment management
  - Stream vs non-stream mode support

## Important Utilities

- **Signal Processing**:
  - Clean separation of input signals from behavior
  - Type-safe signal handling with discriminated unions
  
- **Tool Integration**:
  - Automatic toolbox building from persona configuration
  - Tool execution with proper environment activation
  - Error handling and result reporting

- **Conversation Management**:
  - Automatic message history management
  - System message handling
  - Response formatting and streaming

## Integration Points

Other modules interact with behaviours through:
1. **Signal Types**: For input handling and control flow
2. **SingleTurn**: For individual AI interactions
3. **LoopBehaviour**: For continuous conversation management
4. **Tool Integration**: Through toolbox and environment activation

## Interaction Flow

1. **Input Handling**: Signals are received (prompts, commands, stop)
2. **Conversation Management**: LoopBehaviour maintains conversation state
3. **AI Processing**: SingleTurn handles the actual AI interaction
4. **Tool Execution**: Tools are called as needed based on AI responses
5. **Output**: Results are streamed to the output environment
6. **Continuation**: Loop continues until stop signal is received

## Location Reference
All behavior implementations are in `src/bond/behaviours/` with:
- Signal definitions in `behaviour_signal.py`
- Single turn behavior in `single_turn.py`
- Loop behavior in `loop.py`