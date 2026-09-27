import asyncio
import logging
from argparse import ArgumentParser, Namespace
from asyncio import Queue
from pathlib import Path

from bond.behaviour_flags import BehaviourFlags
from bond.behaviours.async_loop import AsyncAgentLoop
from bond.behaviours.async_turn import AsyncTurnEvent
from bond.config import get_default_persona
from bond.conversation.conversation import Conversation
from bond.runtime import BondRuntime
from bond.tools.tool import ToolCallContext
from bond.tui.app import BondTui
from bond.tui.event_handler import TuiEventHandler
from bond.util import setup_logger

logger = logging.getLogger("bond")


async def run(args: Namespace):
    event_queue: Queue[AsyncTurnEvent] = Queue()

    config_base_path = Path("~/.config/bond").expanduser().absolute()
    data_base_path = (
        Path(args.conversation_path or "~/.local/share/bond").expanduser().absolute()
    )
    last_conv_path = data_base_path / "last-conv.json"

    runtime = BondRuntime.get_instance()
    behaviour_flags = BehaviourFlags(
        save_after_turn=args.no_save_after_turn,
        save_on_quit=not args.temp,
        allow_shell_executions=True,
        stream=True,
    )
    runtime.initialize_dynamic(
        config_base_path, data_base_path, behaviour_flags=behaviour_flags
    )
    config = runtime.get_bond_config()
    conversation = (
        (
            Conversation.load_from_file(last_conv_path)
            if last_conv_path.is_file()
            else Conversation()
        )
        if not args.temp and not args.to and not args.new
        else Conversation()
    )
    if args.to:
        conversation.current_persona = args.to

    persona_id = get_default_persona(config.chat)
    tool_call_context = ToolCallContext.default(persona_id, True)
    loop = AsyncAgentLoop(
        runtime,
        conversation,
        tool_call_context,
        event_queue,
        persona_id,
        config.user_name,
        not args.no_save_after_turn,
    )
    event_handler = TuiEventHandler(event_queue)
    app = BondTui(loop, event_handler)
    event_handler.link(app)
    await app.run_async()


def main():
    parser = ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--temp", action="store_true")
    parser.add_argument("--conversation-path", type=str)
    parser.add_argument("--no-save-after-turn", action="store_true")
    parser.add_argument("--to", type=str)
    parser.add_argument("--new", action="store_true")
    args = parser.parse_args()
    setup_logger(args.debug, "talk.log")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
