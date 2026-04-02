# Issue: Event Handling Refactor

## Problem Description
The `_handle_event` method in `BondTui` (src/bond/tui/app.py) is monolithic and handles many event types (e.g., `stream_start`, `tool_call_result`, `confirmation_request`). This makes the code:
- **Hard to read**: The method is long and complex.
- **Hard to maintain**: Adding new event types requires modifying a single large method.
- **Prone to errors**: Changes to one event type might inadvertently affect others.

## Current Implementation
The `_handle_event` method currently looks like this:
```python
def _handle_event(self, event: BehaviourEvent):
    if event.type == "notify":
        self.notify(event.message)
    elif event.type == "stream_start":
        self._ensure_open_message(event.agent_name, overwrite=False)
        self.status_bar.status = "Responding"
    elif event.type == "stream_end":
        self._last_assistant_message = self._current_open_message
        self._current_open_message = None
        self._allow_user_input = True
        self.status_bar.status = "Idle"
    elif event.type == "stream_chunk":
        # ... handle stream chunk
    elif event.type == "completion_response":
        # ... handle completion response
    elif event.type == "confirmation_request":
        # TODO: implement
        event._value.set_result(False)
    elif event.type == "tool_call_result":
        # ... handle tool call result
    elif event.type == "update_persona":
        # ... update persona
    elif event.type == "clear_log":
        self.clear_log()
    elif event.type == "sync_log":
        self.synchronize(event.conversation, event.message_count)
    elif event.type == "block":
        self._allow_user_input = False
    elif event.type == "release":
        self._allow_user_input = True
    else:
        self.notify(f"Invalid event type: {event.type}", severity="error")
```

## Proposed Solution
Refactor `_handle_event` into smaller, dedicated methods for each event type. This will:
- Improve readability by breaking down the logic.
- Make the code easier to maintain and extend.
- Reduce the risk of errors when modifying event handling.

### Implementation Plan
1. **Extract Event Handlers**: Create dedicated methods for each event type:
   - `_handle_notify_event(event: BehaviourEvent)`
   - `_handle_stream_start_event(event: BehaviourEvent)`
   - `_handle_stream_end_event(event: BehaviourEvent)`
   - `_handle_stream_chunk_event(event: BehaviourEvent)`
   - `_handle_completion_response_event(event: BehaviourEvent)`
   - `_handle_confirmation_request_event(event: BehaviourEvent)`
   - `_handle_tool_call_result_event(event: BehaviourEvent)`
   - `_handle_update_persona_event(event: BehaviourEvent)`
   - `_handle_clear_log_event(event: BehaviourEvent)`
   - `_handle_sync_log_event(event: BehaviourEvent)`
   - `_handle_block_event(event: BehaviourEvent)`
   - `_handle_release_event(event: BehaviourEvent)`
   - `_handle_invalid_event(event: BehaviourEvent)`

2. **Update `_handle_event`**: Modify the method to delegate to the appropriate handler:
   ```python
   def _handle_event(self, event: BehaviourEvent):
       try:
           handler = getattr(self, f"_handle_{event.type}_event", self._handle_invalid_event)
           handler(event)
       except Exception as e:
           self.notify(f"Error handling event: {e}", severity="error")
   ```

3. **Update Event Handling Logic**: Move the logic for each event type into its dedicated method.

4. **Testing**: Add unit tests to ensure each handler works as expected.

## Expected Outcome
- The `_handle_event` method will be reduced to a simple dispatcher.
- Each event type will have its own dedicated method, making the code easier to understand and maintain.
- The risk of introducing bugs when modifying event handling will be reduced.

## Additional Notes
- This refactor will not change the behavior of the application, only its internal structure.
- The new methods should be documented with docstrings to explain their purpose.
