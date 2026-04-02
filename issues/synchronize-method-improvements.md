# Issue: Improve `synchronize` Method Efficiency

## Problem Description
The `synchronize` method in `BondTui` (src/bond/tui/app.py) clears the chat log and repopulates it from the `Conversation` object. This approach is:
- **Inefficient**: For large conversations, clearing and repopulating the chat log is slow.
- **Unnecessary**: The chat log can be updated incrementally without clearing it.
- **Disruptive**: Users see the chat log disappear and repopulate, which is jarring.

### Specific Issues
1. **Performance**: The `synchronize` method iterates over the entire conversation history, which can be slow for large conversations.
2. **User Experience**: The chat log flickers or disappears briefly during synchronization.
3. **State Management**: The method does not leverage shared state (e.g., `TuiState`), leading to potential inconsistencies.

## Current Implementation
The `synchronize` method in `BondTui`:
```python
def synchronize(self, conversation: Conversation, length: int | None = None):
    self.clear_log()
    for message in conversation.history[-length if length is not None else 0 :]:
        if message.message.content is not None:
            self._handle_message_content(
                message.message.content, message.message.role, message.author
            )
    if self.chat_log.is_mounted:
        self.chat_log.scroll_end(animate=False)
```

### Problems
1. **`clear_log`**: Clears the entire chat log, including all rendered widgets.
2. **Iteration**: Loops over the entire conversation history, even if only a few messages have changed.
3. **No Incremental Updates**: Does not support adding or updating individual messages.

## Proposed Solution
Refactor the `synchronize` method to:
1. **Support Incremental Updates**: Only update the chat log if new messages are added or existing messages are modified.
2. **Avoid Clearing the Log**: Preserve the existing chat log and update it incrementally.
3. **Leverage Shared State**: Use a shared state object (e.g., `TuiState`) to track changes.

### Implementation Plan

#### 1. Introduce a Shared State Object
Use the `TuiState` class (from the [Shared State Issue](issues/shared-state.md)) to track the current state of the chat log:
```python
class TuiState:
    def __init__(self):
        self.messages: list[ChatMessage] = []
        self.last_updated_index: int = 0  # Track the last synced message index
```

#### 2. Refactor `synchronize` for Incremental Updates
Update the method to only render new or updated messages:
```python
def synchronize(self, conversation: Conversation, length: int | None = None):
    # Determine the range of messages to sync
    start_index = self.state.last_updated_index
    end_index = len(conversation.history)
    
    if length is not None:
        end_index = min(end_index, start_index + length)
    
    # Only process new or updated messages
    for message in conversation.history[start_index:end_index]:
        if message.message.content is not None:
            self._handle_message_content(
                message.message.content, message.message.role, message.author
            )
    
    # Update the last synced index
    self.state.last_updated_index = end_index
    
    # Scroll to the end of the chat log
    if self.chat_log.is_mounted:
        self.chat_log.scroll_end(animate=False)
```

#### 3. Add a `clear_log` Method for Full Resets
Keep the `clear_log` method for cases where a full reset is needed (e.g., starting a new conversation):
```python
def clear_log(self):
    self.state.clear_messages()
    if self.chat_log.is_mounted:
        self.chat_log.remove_children()
    self.state.last_updated_index = 0
```

#### 4. Update `synchronize` in `TuiCommandHandler`
Ensure the `TuiCommandHandler` emits the correct events for synchronization:
```python
def load(self, args: Namespace):
    self.event_queue.put(BlockEvent())
    super().load(args)
    self.event_queue.put(
        SyncLogEvent(conversation=self.beh.conversation, message_count=None)
    )
    self.event_queue.put(ReleaseEvent())
```

#### 5. Optimize `_handle_message_content`
Ensure the method efficiently appends content to existing messages:
```python
def _handle_message_content(
    self,
    content: list[AssistantMessageChunk] | list[SystemMessageChunk],
    role: Literal["user", "tool", "assistant", "system"],
    author: str | None,
):
    if role == "tool":
        msg = self.state._ensure_open_message(author, overwrite=False)
        msg.append_tool_result(
            " ".join([c.text for c in content if isinstance(c, TextChunk)]),
            name=author,
        )
    elif role == "assistant":
        msg = self.state._ensure_open_message(author, overwrite=False)
        self._handle_message_chunks(msg, content)
    elif role == "system":
        msg = ChatMessage(author or "System", role)
        self._handle_message_chunks(msg, content)
        self.state.add_message(msg)
    elif role == "user":
        msg = ChatMessage(author or "User", role)
        self._handle_message_chunks(msg, content)
        self.state.add_message(msg)
```

#### 6. Testing
Add unit tests for the refactored `synchronize` method:
```python
# tests/test_synchronize.py
from bond.tui.app import BondTui
from bond.conversation.conversation import Conversation


def test_synchronize_incremental():
    state = TuiState()
    app = BondTui(signal_queue=None, event_queue=None, starting_persona=None)
    app.state = state
    
    # Simulate a conversation with 3 messages
    conversation = Conversation()
    conversation.add_user_message("Hello")
    conversation.add_assistant_message("Hi there!")
    conversation.add_user_message("How are you?")
    
    # Sync the first 2 messages
    app.synchronize(conversation, length=2)
    assert len(app.state.messages) == 2
    
    # Sync the remaining message
    app.synchronize(conversation, length=1)
    assert len(app.state.messages) == 3


def test_synchronize_full():
    state = TuiState()
    app = BondTui(signal_queue=None, event_queue=None, starting_persona=None)
    app.state = state
    
    # Simulate a conversation with 3 messages
    conversation = Conversation()
    conversation.add_user_message("Hello")
    conversation.add_assistant_message("Hi there!")
    conversation.add_user_message("How are you?")
    
    # Sync all messages
    app.synchronize(conversation)
    assert len(app.state.messages) == 3


def test_clear_log():
    state = TuiState()
    app = BondTui(signal_queue=None, event_queue=None, starting_persona=None)
    app.state = state
    
    # Add a message
    conversation = Conversation()
    conversation.add_user_message("Hello")
    app.synchronize(conversation)
    assert len(app.state.messages) == 1
    
    # Clear the log
    app.clear_log()
    assert len(app.state.messages) == 0
    assert app.state.last_updated_index == 0
```

## Expected Outcome
- The `synchronize` method will **only update new or changed messages**, improving performance.
- The chat log will **not flicker or disappear** during synchronization.
- The method will **leverage shared state** to avoid inconsistencies.
- The user experience will be **smoother** and more responsive.

## Additional Notes
- This change should be made in conjunction with the [Shared State Issue](issues/shared-state.md) to ensure consistency.
- Consider adding a **debounce mechanism** for rapid synchronization requests (e.g., during streaming).
- Document the new behavior of `synchronize` to explain its purpose and usage.
