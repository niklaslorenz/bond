import asyncio
import logging
from argparse import ArgumentParser, Namespace
from asyncio import Queue
from pathlib import Path

from bond.behaviours.async_loop import AsyncAgentLoop
from bond.behaviours.async_turn import AsyncTurnEvent
from bond.config import get_default_persona
from bond.conversation.conversation import Conversation
from bond.runtime import BondRuntime
from bond.tools.tool import ToolCallContext
from bond.tui.app import BondTui
from bond.util import setup_logger

logger = logging.getLogger("bond")


async def run(args: Namespace):
    event_queue: Queue[AsyncTurnEvent] = Queue()

    config_base_path = Path("~/.config/bond").expanduser().absolute()
    data_base_path = (
        Path(args.conversation_path or "~/.local/share/bond").expanduser().absolute()
    )
    conversation_base_path = data_base_path / "conversations"
    last_conv_path = data_base_path / "last-conv.json"

    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic(config_base_path)
    config = runtime.get_bond_config()
    conversation = (
        (
            Conversation.load_from_file(last_conv_path)
            if last_conv_path.is_file()
            else Conversation()
        )
        if not args.temp and not args.to
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
        True,
        True,
        config.user_name,
        not args.no_safe_after_turn,
    )
    app = BondTui(loop)
    await app.start_tui()


def main():
    parser = ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--temp", action="store_true")
    parser.add_argument("--conversation-path", type=str)
    parser.add_argument("--no-save-after-turn", action="store_true")
    parser.add_argument("--to", type=str)
    args = parser.parse_args()
    setup_logger(args.debug, "talk.log")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
