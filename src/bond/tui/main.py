import asyncio
import logging
import threading
from argparse import ArgumentParser
from pathlib import Path
from queue import Queue

from bond.behaviours.loop import LoopBehaviour
from bond.behaviours.types import BehaviourEvent, BehaviourSignal
from bond.config import BondConfig, get_default_persona
from bond.conversation.conversation import Conversation
from bond.runtime import BondRuntime
from bond.tools.tool import ToolCallContext
from bond.tui.app import BondTui
from bond.tui.default_state_machine import DefaultTuiStateMachine
from bond.tui.environment.tui_command_handler import TuiCommandHandler
from bond.tui.environment.tui_signal_receiver import TuiSignalReceiver
from bond.tui.types import ITuiEvent

logger = logging.getLogger("bond")


def setup_logger():
    debug_dir = Path("~/.local/share/bond/logs/").expanduser().absolute()
    debug_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=(debug_dir / "app.log").as_posix(),
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger.setLevel(logging.DEBUG)


async def run(conversation_path: str | None, save_after_turn: bool):
    signal_queue: Queue[BehaviourSignal] = Queue()
    event_queue: Queue[BehaviourEvent | ITuiEvent] = Queue()

    config_base_path = Path("~/.config/bond").expanduser().absolute()
    data_base_path = (
        Path(conversation_path or "~/.local/share/bond").expanduser().absolute()
    )
    conversation_base_path = data_base_path / "conversations"
    last_conv_path = data_base_path / "last-conv.json"

    config = BondConfig.load_from(config_base_path / "config.json")
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic(config_base_path)
    conversation = (
        Conversation.model_validate_json(last_conv_path.read_text())
        if last_conv_path.is_file()
        else Conversation()
    )

    state_machine = DefaultTuiStateMachine(
        signal_queue=signal_queue,
        event_queue=event_queue,
    )
    app = BondTui(state_machine)
    state_machine.run(app)
    event_handler = lambda event: state_machine.handle_event(event)

    receiver = TuiSignalReceiver(signal_queue)

    cmd_handler = TuiCommandHandler(
        event_handler=event_handler,
        signal_handler=receiver,
        conversation_base_path=conversation_base_path,
        last_conv_path=last_conv_path,
        available_personas=config.chat.personas,
        save_on_quit=True,
    )

    persona_id = get_default_persona(config.chat)

    tool_call_context = ToolCallContext.default(persona_id, True)

    loop = LoopBehaviour(
        runtime=runtime,
        conversation=conversation,
        event_handler=event_handler,
        signal_receiver=receiver,
        command_handler=cmd_handler,
        tool_call_context=tool_call_context,
        persona_id=persona_id,
        stream=True,
        allow_shell_executions=True,
        user_name=config.user_name,
        allowed_personas=config.chat.personas,
    )
    cmd_handler.link(loop)

    app.synchronize(conversation)

    thread = threading.Thread(target=loop.run, daemon=True)
    thread.start()
    await app.start_tui()


def main():
    parser = ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--conversation-path", type=str)
    parser.add_argument("--no-save-after-turn", action="store_true")
    args = parser.parse_args()
    if args.debug:
        setup_logger()
    asyncio.run(run(args.conversation_path, not args.no_save_after_turn))


if __name__ == "__main__":
    main()
