# Conversation Module Summary

## Overview
The `src/bond/conversation` module handles message types, conversation state, and message history for the chatbot system.

## Key Components

### 1. Message Types (`types.py`)
Defines all message types used in conversations:

- **TextChunk**: Basic text content
- **ReferenceChunk**: References to external sources
- **ToolReferenceChunk**: References to tools/functions
- **ThinkChunk**: Internal reasoning/thinking content
- **FunctionCall**: Function/tool calls with arguments
- **ToolCall**: Wrapper for function calls
- **AssistantMessage**: Messages from assistant
- **UserMessage**: Messages from user
- **SystemMessage**: System-level messages
- **ToolMessage**: Messages from tools

### 2. ConversationMessage (`conversation.py`)
- **Purpose**: Wrapper for messages with author information
- **Important Methods**:
  - `create_system_message()`: Create system messages
  - `create_user_message()`: Create user messages
  - `create_tool_response_message()`: Create tool response messages
- **Usage**: Building blocks for conversation history

### 3. Conversation (`conversation.py`)
- **Purpose**: Manages conversation history
- **Key Attributes**:
  - `history`: List of conversation messages
  - `name`: Optional conversation name
- **Important Methods**:
  - `add_message()`: Add new message to history
  - `get_chat_completion_messages()`: Get messages for chat completion
- **Usage**: Core conversation state management

## Important Utilities

- Message creation helpers in `ConversationMessage`
- Message type validation and serialization in `types.py`
- Conversion between different message formats

## Integration Points

Other modules will likely interact with:
1. Message types for constructing conversations
2. `ConversationMessage` for message handling
3. `Conversation` for conversation state management

## Location Reference
All definitions are in `src/bond/conversation/` module files.