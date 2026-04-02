# Issue: Testing for TUI Components

## Problem Description
The TUI currently lacks **unit tests** and **integration tests**, which makes it difficult to:
- Ensure reliability and correctness of components.
- Catch regressions when refactoring or adding new features.
- Verify that widgets render correctly and handle events as expected.

### Specific Issues
1. **No Unit Tests**: There are no tests for individual widgets (e.g., `ChatMessage`, `StatusBar`, `InputBar`).
2. **No Integration Tests**: There are no tests for interactions between components (e.g., event handling, command processing).
3. **No End-to-End Tests**: There are no tests for the entire TUI workflow (e.g., launching the app, sending messages, executing commands).
4. **No Regression Testing**: Changes to the TUI could introduce bugs that go unnoticed without tests.

## Current Implementation
The TUI is implemented using the **Textual** framework, which provides utilities for testing:
- `textual.app.App` can be tested using `textual.run_test`.
- Widgets can be rendered and inspected in tests.
- Events can be simulated and verified.

However, there are **no tests** in the repository.

## Proposed Solution
Add a **testing framework** for the TUI using Textual's testing utilities. This will:
- Ensure reliability and correctness of components.
- Catch regressions early.
- Make it easier to refactor and extend the TUI.

### Implementation Plan

#### 1. Set Up Testing Infrastructure
Create a `tests/` directory and configure `pytest`:
```bash
mkdir tests
touch tests/__init__.py
touch tests/conftest.py
```

Add `pytest` and `textual` to the project's dev dependencies in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
python_files = "test_*.py"
```

#### 2. Write Unit Tests for Widgets
Test individual widgets (e.g., `ChatMessage`, `StatusBar`, `InputBar`):
```python
# tests/test_widgets.py
from textual.app import App
from bond.tui.widgets import ChatMessage, StatusBar, InputBar


def test_chat_message_rendering():
    msg = ChatMessage("User", "user")
    msg.add_text_block("Hello, world!")
    assert msg.text == "Hello, world!"


def test_status_bar_rendering():
    status_bar = StatusBar()
    status_bar.persona = "TestPersona"
    status_bar.provider = "TestProvider"
    status_bar.status = "Idle"
    status_bar.context_length = 10
    
    # Render the status bar and verify its content
    rendered = status_bar.render()
    assert "TestPersona" in rendered.plain
    assert "TestProvider" in rendered.plain
    assert "Idle" in rendered.plain
    assert "10" in rendered.plain


def test_input_bar_focus():
    input_bar = InputBar()
    assert input_bar.input_field.has_focus
```

#### 3. Write Integration Tests for Event Handling
Test interactions between components (e.g., event handling, command processing):
```python
# tests/test_event_handling.py
from queue import Queue
from bond.tui.app import BondTui
from bond.behaviours.behaviour_signal import BehaviourSignal
from bond.io.queue_env import BehaviourEvent


def test_handle_stream_event():
    signal_queue = Queue[BehaviourSignal]()
    event_queue = Queue[BehaviourEvent]()
    
    app = BondTui(signal_queue, event_queue, starting_persona=None)
    
    # Simulate a stream_start event
    event = BehaviourEvent(type="stream_start", agent_name="Assistant")
    app._handle_event(event)
    
    assert app.status_bar.status == "Responding"
    assert app._current_open_message is not None


def test_handle_tool_call_result_event():
    signal_queue = Queue[BehaviourSignal]()
    event_queue = Queue[BehaviourEvent]()
    
    app = BondTui(signal_queue, event_queue, starting_persona=None)
    
    # Simulate a tool_call_result event
    event = BehaviourEvent(
        type="tool_call_result",
        tool_call={"function": {"name": "test_tool"}},
        tool_return="test result"
    )
    app._handle_event(event)
    
    assert len(app.messages) > 0
    assert app.messages[-1].elements[-1].text == "test result"
```

#### 4. Write End-to-End Tests
Test the entire TUI workflow (e.g., launching the app, sending messages, executing commands):
```python
# tests/test_tui_workflow.py
from textual.app import App
from bond.tui.app import BondTui
from bond.behaviours.behaviour_signal import BehaviourSignal
from bond.io.queue_env import BehaviourEvent


async def test_tui_launch_and_input():
    signal_queue = Queue[BehaviourSignal]()
    event_queue = Queue[BehaviourEvent]()
    
    app = BondTui(signal_queue, event_queue, starting_persona=None)
    async with app.run_test() as pilot:
        # Simulate user input
        await pilot.press("a")
        await pilot.press("enter")
        
        # Verify the input was processed
        assert app.input_bar.input_field.text == "a"


async def test_tui_command_handling():
    signal_queue = Queue[BehaviourSignal]()
    event_queue = Queue[BehaviourEvent]()
    
    app = BondTui(signal_queue, event_queue, starting_persona=None)
    async with app.run_test() as pilot:
        # Simulate a command
        await pilot.press(":")
        await pilot.press("s")
        await pilot.press("a")
        await pilot.press("v")
        await pilot.press("e")
        await pilot.press("enter")
        
        # Verify the command was processed
        assert signal_queue.qsize() == 1
        signal = signal_queue.get()
        assert signal.type == "command"
        assert signal.command == "save"
```

#### 5. Test Command Handler
Test the `TuiCommandHandler` to ensure commands are processed correctly:
```python
# tests/test_command_handler.py
from pathlib import Path
from queue import Queue
from bond.tui.command_handler import TuiCommandHandler
from bond.io.queue_env import BehaviourEvent


def test_save_command():
    event_queue = Queue[BehaviourEvent]()
    handler = TuiCommandHandler(
        conversation_base_path=Path("/tmp"),
        last_conv_path=Path("/tmp/last-conv.json"),
        available_personas=["test_persona"],
    )
    handler.link(event_queue, None)
    
    # Simulate a save command
    handler.save(Namespace(name="test"))
    
    # Verify the event was emitted
    assert event_queue.qsize() == 1
    event = event_queue.get()
    assert event.type == "notify"
    assert "Saved as 'test'" in event.message
```

#### 6. Test CSS Styling
Verify that the TUI's CSS styles are applied correctly:
```python
# tests/test_css_styling.py
from textual.app import App
from bond.tui.app import BondTui


async def test_css_styling():
    app = BondTui(signal_queue=None, event_queue=None, starting_persona=None)
    async with app.run_test() as pilot:
        # Verify the CSS is loaded
        assert app.css is not None
        
        # Verify a widget's style
        chat_log = app.query_one("#chat-log")
        assert chat_log.styles.scrollbar_gutter == "stable"
```

## Expected Outcome
- The TUI will have a **comprehensive test suite** covering unit, integration, and end-to-end tests.
- Regressions will be caught early during development.
- Refactoring and extending the TUI will be safer and easier.
- The codebase will be more maintainable and reliable.

## Additional Notes
- Use `pytest` for running tests and `textual.run_test` for simulating user interactions.
- Add tests incrementally as new features are added.
- Consider using **GitHub Actions** to run tests automatically on every push.
