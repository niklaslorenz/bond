# Issue: Command Handler Refactor

## Problem Description
The `TuiCommandHandler` class (src/bond/tui/command_handler.py) extends `DefaultCommandHandler` and duplicates logic for handling commands. This leads to:
- **Code Duplication**: Logic for commands like `save`, `load`, and `new` is repeated in both `DefaultCommandHandler` and `TuiCommandHandler`.
- **Maintenance Issues**: Changes to command handling require updates in multiple places.
- **Poor Extensibility**: Adding new commands or modifying existing ones is cumbersome.

### Specific Issues
1. **Inheritance**: `TuiCommandHandler` inherits from `DefaultCommandHandler` but overrides methods like `quit`, `load`, `save`, and `new`.
2. **Event Emission**: `TuiCommandHandler` emits `BehaviourEvent` instances to update the TUI, but this logic is mixed with the base class.
3. **Lack of Abstraction**: There is no clear separation between TUI-specific and generic command handling logic.

## Current Implementation
### TuiCommandHandler
```python
class TuiCommandHandler(DefaultCommandHandler):
    event_queue: Queue[BehaviourEvent]
    beh: LoopBehaviour

    def __init__(
        self,
        conversation_base_path: Path,
        last_conv_path: Path,
        available_personas: list[str],
        save_on_quit: bool = False,
    ):
        super().__init__(
            conversation_base_path,
            last_conv_path,
            available_personas,
            save_on_quit,
        )

    def link(self, event_queue: Queue[BehaviourEvent], beh: LoopBehaviour):
        self.event_queue = event_queue
        self.beh = beh

    def quit(self, args: Namespace):
        super().quit(args)
        self.event_queue.put(StopEvent())

    def load(self, args: Namespace):
        self.event_queue.put(BlockEvent())
        super().load(args)
        self.event_queue.put(
            SyncLogEvent(conversation=self.beh.conversation, message_count=None)
        )
        self.event_queue.put(ReleaseEvent())

    def save(self, args: Namespace):
        super().save(args)
        if args.name is not None:
            self.event_queue.put(NotifyEvent(message=f"Saved as '{args.name}'"))

    def new(self, args: Namespace):
        super().new(args)
        self.event_queue.put(ClearLogEvent())

    # ... other methods
```

### DefaultCommandHandler
The base class handles generic command logic (e.g., saving conversations, loading personas).

## Proposed Solution
Refactor the command handling system to:
1. **Reduce Duplication**: Extract TUI-specific logic into a mixin or separate class.
2. **Improve Extensibility**: Use a plugin system or strategy pattern for command handling.
3. **Simplify Maintenance**: Centralize command logic in a single place.

### Implementation Plan

#### 1. Extract TUI-Specific Logic
Create a `TuiCommandMixin` class to handle TUI-specific command logic:
```python
class TuiCommandMixin:
    """Mixin for TUI-specific command handling."""

    event_queue: Queue[BehaviourEvent]
    beh: LoopBehaviour

    def __init__(self):
        self.event_queue = None
        self.beh = None

    def link(self, event_queue: Queue[BehaviourEvent], beh: LoopBehaviour):
        self.event_queue = event_queue
        self.beh = beh

    def quit(self, args: Namespace):
        self.event_queue.put(StopEvent())

    def load(self, args: Namespace):
        self.event_queue.put(BlockEvent())
        # ... load logic from DefaultCommandHandler
        self.event_queue.put(
            SyncLogEvent(conversation=self.beh.conversation, message_count=None)
        )
        self.event_queue.put(ReleaseEvent())

    def save(self, args: Namespace):
        # ... save logic from DefaultCommandHandler
        if args.name is not None:
            self.event_queue.put(NotifyEvent(message=f"Saved as '{args.name}'"))

    def new(self, args: Namespace):
        # ... new logic from DefaultCommandHandler
        self.event_queue.put(ClearLogEvent())
```

#### 2. Refactor TuiCommandHandler
Update `TuiCommandHandler` to use the mixin:
```python
class TuiCommandHandler(DefaultCommandHandler, TuiCommandMixin):
    def __init__(
        self,
        conversation_base_path: Path,
        last_conv_path: Path,
        available_personas: list[str],
        save_on_quit: bool = False,
    ):
        DefaultCommandHandler.__init__(
            self,
            conversation_base_path,
            last_conv_path,
            available_personas,
            save_on_quit,
        )
        TuiCommandMixin.__init__(self)

    def quit(self, args: Namespace):
        TuiCommandMixin.quit(self, args)
        super().quit(args)

    def load(self, args: Namespace):
        TuiCommandMixin.load(self, args)
        super().load(args)

    def save(self, args: Namespace):
        TuiCommandMixin.save(self, args)
        super().save(args)

    def new(self, args: Namespace):
        TuiCommandMixin.new(self, args)
        super().new(args)
```

#### 3. Use Composition Over Inheritance
Alternatively, use composition to avoid the complexity of multiple inheritance:
```python
class TuiCommandHandler:
    def __init__(
        self,
        conversation_base_path: Path,
        last_conv_path: Path,
        available_personas: list[str],
        save_on_quit: bool = False,
    ):
        self.default_handler = DefaultCommandHandler(
            conversation_base_path,
            last_conv_path,
            available_personas,
            save_on_quit,
        )
        self.tui_mixin = TuiCommandMixin()

    def link(self, event_queue: Queue[BehaviourEvent], beh: LoopBehaviour):
        self.tui_mixin.link(event_queue, beh)

    def quit(self, args: Namespace):
        self.tui_mixin.quit(args)
        self.default_handler.quit(args)

    def load(self, args: Namespace):
        self.tui_mixin.load(args)
        self.default_handler.load(args)

    # ... other methods
```

#### 4. Centralize Command Logic
Move common command logic (e.g., `save`, `load`) into a `CommandRegistry` class:
```python
class CommandRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, name: str, handler: Callable[[Namespace], None]):
        self.commands[name] = handler

    def execute(self, name: str, args: Namespace):
        if name in self.commands:
            self.commands[name](args)
        else:
            raise ValueError(f"Unknown command: {name}")
```

Update `TuiCommandHandler` to use the registry:
```python
class TuiCommandHandler:
    def __init__(self):
        self.registry = CommandRegistry()
        self._register_commands()

    def _register_commands(self):
        self.registry.register("quit", self._handle_quit)
        self.registry.register("save", self._handle_save)
        self.registry.register("load", self._handle_load)
        # ... other commands

    def _handle_quit(self, args: Namespace):
        self.event_queue.put(StopEvent())

    def _handle_save(self, args: Namespace):
        # ... save logic
        if args.name is not None:
            self.event_queue.put(NotifyEvent(message=f"Saved as '{args.name}'"))

    def execute_command(self, command: str, args: Namespace):
        self.registry.execute(command, args)
```

#### 5. Testing
Add unit tests for the refactored command handler:
```python
# tests/test_command_handler.py
from bond.tui.command_handler import TuiCommandHandler


def test_save_command():
    handler = TuiCommandHandler(
        conversation_base_path=Path("/tmp"),
        last_conv_path=Path("/tmp/last-conv.json"),
        available_personas=["test_persona"],
    )
    handler.link(event_queue=Queue(), beh=None)
    
    # Simulate a save command
    handler.save(Namespace(name="test"))
    
    # Verify the event was emitted
    assert handler.event_queue.qsize() == 1
    event = handler.event_queue.get()
    assert event.type == "notify"
    assert "Saved as 'test'" in event.message
```

## Expected Outcome
- The `TuiCommandHandler` will be **simpler** and **more maintainable**.
- Logic for TUI-specific commands will be **centralized** in a mixin or registry.
- The codebase will be **easier to extend** with new commands.
- Duplication will be **reduced**, making the system more robust.

## Additional Notes
- The refactor should not change the behavior of the application, only its internal structure.
- Consider using **dependency injection** to make the command handler more flexible.
- Document the new command handling system to explain its purpose and usage.
