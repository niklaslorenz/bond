# IO Module Summary

## Overview
The `src/bond/io` module handles input/output operations, streaming responses, and environment interactions for the chatbot system. It provides various implementations for outputting agent responses and managing user interaction.

## Core Components

### 1. Agent Output Environments (`aoe.py`)
Defines the interface and implementations for agent output handling:

- **AgentOutputEnvironment (Protocol)**:
  - Defines the interface for agent output handling:
    - `start_streaming_response()`: Begin streaming output
    - `end_streaming_response()`: End streaming output
    - `handle_response_chunk()`: Process individual response chunks
    - `handle_response()`: Process complete responses

- **StringAoe**: Base implementation for string-based output
  - Handles text and thought output streams
  - Tracks unfinished text/thoughts for proper formatting
  - Methods for handling different message chunks

- **QueueAoe**: Queue-based output handler
  - Converts output operations into queue events
  - Used for asynchronous output handling
  - Integrates with event queues for inter-process communication

### 2. Stream Utilities (`stream.py`)
Provides stream wrappers and utilities:

- **WritethroughWrapper**: TextIO wrapper that flushes after each write
  - Ensures immediate output visibility
  - Useful for logging and debugging

- **ThoughtWrapper**: TextIO wrapper that adds think tags
  - Automatically wraps content with `<think>` tags
  - Used for distinguishing internal thoughts from output

### 3. Queue-Based IO (`queue_env.py`)
Implements queue-based communication and environment:

- **Behaviour Events**:
  - `StreamStartEvent`, `StreamEndEvent`, `StreamChunkEvent`: For streaming responses
  - `CompletionResponseEvent`: For complete responses
  - `ConfirmationRequestEvent`: For user confirmation requests
  - `ToolCallResultEvent`: For tool execution results
  - `NotifyEvent`: For general notifications
  - `UpdatePersonaEvent`: For persona updates
  - `BlockEvent`, `ReleaseEvent`: For flow control
  - `ClearLogEvent`, `SyncLogEvent`: For log management

- **QueueAoe**: Queue-based output handler (see above)

- **QueueToolEnvironment**: Tool environment using queues
  - Implements `ToolEnvironment` protocol via queue
  - Handles confirmation requests through queue events
  - Manages tool execution results

- **QueueSignalReceiver**: Converts queue signals to behaviour signals

- **QueueNotifier**: Converts notifications to queue events

### 4. Standard IO Implementations (`stdenv.py`)
Provides standard I/O implementations:

- **StdAoe**: Standard output handler extending StringAoe
  - Uses system stdout for output
  - Wraps stdout in WritethroughWrapper

- **StdSignalReceiver**: Standard input signal receiver
  - Reads user input and converts to signals
  - Supports command mode (prefix with ':')
  - Allows persona-based interaction

- **StdNotifier**: Standard notification handler
  - Simple print-based notifications

- **StdIoToolEnvironment**: Standard tool environment
  - Handles tool execution in standard environment
  - Supports interactive confirmation
  - Manages output visibility options
  - Implements all ToolEnvironment methods

## Important Utilities

- **Stream Management**:
  - Consistent handling of streaming vs complete responses
  - Proper formatting of thoughts vs regular output
  
- **Environment Integration**:
  - Tool environments that work with different I/O backends
  - Signal handling for user interaction
  
- **Queue-Based Communication**:
  - Event-driven architecture for async operations
  - Type-safe event handling with BehaviourEvent

## Integration Points

Other modules interact with IO through:
1. **AgentOutputEnvironment**: For output handling
2. **ToolEnvironment**: For tool execution context
3. **Signal Handling**: For user interaction
4. **Queue Events**: For asynchronous communication

## Location Reference
All IO implementations are in `src/bond/io/` with:
- Core interfaces in `aoe.py`
- Stream utilities in `stream.py`
- Queue-based implementations in `queue_env.py`
- Standard implementations in `stdenv.py`