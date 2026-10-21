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
from bond.tui.event_handler import TuiEventHandler
from bond.util import setup_logger

logger = logging.getLogger("bond")


async def run(args: Namespace):
    event_queue: Queue[AsyncTurnEvent] = Queue()

    config_base_path = Path("~/.config/bond").expanduser().absolute()
    data_base_path = (
        Path(args.conversation_path or "~/.local/share/bond").expanduser().absolute()
    )

    save_after_turn = args.no_save_after_turn
    save_on_quit = not args.temp
    allow_shell_executions = True
    stream = True

    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic(config_base_path, data_base_path)
    config = runtime.get_bond_config()
    logger.debug(
        f"Found last conversation: {Conversation.exists('last-conv', data_base_path)}"
    )
    conversation = (
        Conversation.load("last-conv", data_base_path)
        if Conversation.exists("last-conv", data_base_path)
        and not args.temp
        and not args.to
        and not args.new
        else Conversation()
    )
    logger.debug(
        f"conversation loading gates: temp: {args.temp}, to: {args.to}, new: {args.new}"
    )
    logger.debug(
        f"Number of turns loaded: {sum([len(ep.turns) for ep in conversation.episodes])}"
    )
    if args.to:
        conversation.persona = args.to

    event_loop = asyncio.get_event_loop()
    persona_id = get_default_persona(config.chat)
    tool_call_context = ToolCallContext.async_default(
        None, True, conversation, event_loop, event_queue
    )
    loop = AsyncAgentLoop(
        runtime,
        conversation,
        tool_call_context,
        event_queue,
        event_loop,
        persona_id,
        stream=stream,
        allow_shell_executions=allow_shell_executions,
        save_after_turn=save_after_turn,
        stop_on_failure=False,
    )
    event_handler = TuiEventHandler(event_queue)
    app = BondTui(loop, event_handler, save_on_quit)
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
