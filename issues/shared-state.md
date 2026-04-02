# Issue: Shared State Management

## Problem Description
The `BondTui` class (src/bond/tui/app.py) and `TuiCommandHandler` (src/bond/tui/command_handler.py) manage their own state (e.g., `self.messages`, `self._current_open_message`, `self.status_bar.status`). This leads to:
- **Inconsistencies**: The TUI and `LoopBehaviour` might diverge if state is not synchronized.
- **Duplication**: State is duplicated across classes, making it harder to maintain.
- **Complexity**: The `synchronize` method in `BondTui` clears and repopulates the chat log, which is inefficient for large conversations.

## Current Implementation
### BondTui State
- `self.messages`: List of `ChatMessage` instances.
- `self._current_open_message`: The currently open assistant message.
- `self._last_assistant_message`: The last assistant message.
- `self.status_bar.status`: The current status (e.g., "Idle", "Responding").

### TuiCommandHandler State
- Inherits state from `DefaultCommandHandler` (e.g., conversation paths, available personas).
- Emits `BehaviourEvent` instances to update the TUI.

### Synchronization Issues
- The `synchronize` method in `BondTui` clears the chat log and repopulates it from the `Conversation` object. This is inefficient for large conversations.
- There is no shared state object to ensure consistency between the TUI and `LoopBehaviour`.

## Proposed Solution
Introduce a **shared state object** (`TuiState`) to manage state that needs to be synchronized between the TUI and `LoopBehaviour`. This will:
- Ensure consistency between components.
- Reduce duplication and improve maintainability.
- Enable more efficient synchronization (e.g., incremental updates).

### Implementation Plan
1. **Create `TuiState` Class**:
   Define a class to manage shared state:
   ```python
   class TuiState:
       def __init__(self):
           self.messages: list[ChatMessage] = []
           self.current_persona: str | None = None
           self.current_provider: str | None = None
           self.status: str = "Idle"
           self.context_length: int = 0
           self._current_open_message: ChatMessage | None = None
           self._last_assistant_message: ChatMessage | None = None
           
       def clear_messages(self):
           self.messages.clear()
           self._current_open_message = None
           self._last_assistant_message = None
           
       def add_message(self, message: ChatMessage):
           self.messages.append(message)
           if message.role == "assistant":
               self._last_assistant_message = message
           else:
               self._last_assistant_message = None
               self._current_open_message = None
   ```

2. **Update `BondTui`**:
   - Replace `self.messages`, `self._current_open_message`, and `self._last_assistant_message` with `self.state = TuiState()`.
   - Update methods like `add_message`, `clear_log`, and `synchronize` to use the shared state.

3. **Update `TuiCommandHandler`**:
   - Add a reference to `TuiState` and update it when commands are executed (e.g., `clear_log`, `sync_log`).

4. **Update `main.py`**:
   - Pass the `TuiState` instance to both `BondTui` and `TuiCommandHandler`.

5. **Refactor `synchronize`**:
   - Implement incremental updates to avoid clearing and repopulating the chat log.

6. **Testing**:
   - Add unit tests for `TuiState` to ensure state is updated correctly.

## Expected Outcome
- State is centralized in `TuiState`, reducing duplication and improving consistency.
- The `synchronize` method becomes more efficient by supporting incremental updates.
- The TUI and `LoopBehaviour` stay in sync, reducing the risk of inconsistencies.

## Additional Notes
- This change will require updates to multiple classes, so it should be done carefully to avoid breaking existing functionality.
- The `TuiState` class should be documented to explain its purpose and usage.
