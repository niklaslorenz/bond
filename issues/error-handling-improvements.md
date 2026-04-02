# Issue: Error Handling Improvements

## Problem Description
The TUI currently has **minimal error handling**, which could lead to:
- **Crashes**: Unhandled exceptions in event handling or command processing.
- **Poor User Experience**: Users are not informed of errors (e.g., failed event handling).
- **Debugging Difficulties**: Errors are not logged or reported in a user-friendly way.

### Specific Issues
1. **Event Handling**: The `_handle_event` method does not handle exceptions gracefully. If an event handler raises an exception, the entire TUI could crash.
2. **Command Handling**: The `TuiCommandHandler` does not handle errors when executing commands (e.g., `:save`, `:load`).
3. **Thread Crashes**: The `LoopBehaviour` runs in a separate thread, but there is no mechanism to restart it if it crashes.
4. **User Feedback**: Errors are not consistently reported to the user (e.g., via notifications).

## Current Implementation
### Event Handling
The `_handle_event` method in `BondTui` does not handle exceptions:
```python
def _handle_event(self, event: BehaviourEvent):
    if event.type == "notify":
        self.notify(event.message)
    elif event.type == "stream_start":
        self._ensure_open_message(event.agent_name, overwrite=False)
        self.status_bar.status = "Responding"
    # ... other event types
    else:
        self.notify(f"Invalid event type: {event.type}", severity="error")
```

### Command Handling
The `TuiCommandHandler` does not handle errors when executing commands:
```python
def save(self, args: Namespace):
    super().save(args)
    if args.name is not None:
        self.event_queue.put(NotifyEvent(message=f"Saved as '{args.name}'"))
```

### Thread Management
The `main.py` file starts the `LoopBehaviour` in a separate thread but does not handle thread crashes:
```python
thread = threading.Thread(target=loop.run, daemon=True)
thread.start()
```

## Proposed Solution
Improve error handling across the TUI by:
1. Adding **exception handling** to event and command processing.
2. Implementing a **thread recovery mechanism** for the `LoopBehaviour`.
3. Providing **consistent user feedback** for errors.

### Implementation Plan

#### 1. Exception Handling in Event Processing
Update `_handle_event` to catch exceptions and notify the user:
```python
def _handle_event(self, event: BehaviourEvent):
    try:
        if event.type == "notify":
            self.notify(event.message)
        elif event.type == "stream_start":
            self._handle_stream_start_event(event)
        elif event.type == "tool_call_result":
            self._handle_tool_call_result_event(event)
        # ... other event types
        else:
            self.notify(f"Invalid event type: {event.type}", severity="error")
    except Exception as e:
        self.notify(f"Error handling event: {e}", severity="error")
        # Log the error for debugging
        import traceback
        traceback.print_exc()
```

#### 2. Exception Handling in Command Processing
Update `TuiCommandHandler` to handle errors when executing commands:
```python
def save(self, args: Namespace):
    try:
        super().save(args)
        if args.name is not None:
            self.event_queue.put(NotifyEvent(message=f"Saved as '{args.name}'"))
    except Exception as e:
        self.event_queue.put(NotifyEvent(message=f"Failed to save: {e}", severity="error"))
```

#### 3. Thread Recovery Mechanism
Add a mechanism to restart the `LoopBehaviour` thread if it crashes:
```python
class LoopRecovery:
    def __init__(self, loop: LoopBehaviour, event_queue: Queue[BehaviourEvent]):
        self.loop = loop
        self.event_queue = event_queue
        self.thread: threading.Thread | None = None
        self.is_running = False

    def start(self):
        self.is_running = True
        self._start_loop()

    def _start_loop(self):
        def loop_target():
            while self.is_running:
                try:
                    self.loop.run()
                except Exception as e:
                    self.event_queue.put(NotifyEvent(message=f"Loop crashed: {e}", severity="error"))
                    import time
                    time.sleep(1)  # Avoid rapid restarts
                    self._start_loop()

        self.thread = threading.Thread(target=loop_target, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()
```

Update `main.py` to use `LoopRecovery`:
```python
recovery = LoopRecovery(loop, event_queue)
recovery.start()
```

#### 4. Consistent User Feedback
Ensure all errors are reported to the user via `NotifyEvent`:
```python
# Example: Notify the user of a failed event
try:
    self._handle_event(event)
except Exception as e:
    self.notify(f"Failed to handle event: {e}", severity="error")
```

#### 5. Logging
Add logging for debugging purposes:
```python
import logging

logging.basicConfig(filename='bond_tui.log', level=logging.ERROR)

def _handle_event(self, event: BehaviourEvent):
    try:
        # ... event handling logic
    except Exception as e:
        logging.error(f"Error handling event {event.type}: {e}")
        self.notify(f"Error: {e}", severity="error")
```

## Expected Outcome
- The TUI will handle exceptions gracefully, preventing crashes.
- Users will be informed of errors via notifications.
- The `LoopBehaviour` thread will recover automatically if it crashes.
- Debugging will be easier with proper error logging.

## Additional Notes
- This change will improve the reliability and user experience of the TUI.
- The error handling should be consistent across all components (TUI, command handler, and loop).
- Consider adding a debug mode to enable verbose logging.
