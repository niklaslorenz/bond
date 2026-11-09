import asyncio
import os
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from returns.result import Failure

from bond import util
from bond.behaviours.async_loop import AsyncAgentLoop
from bond.behaviours.async_turn import AsyncTurnEvent
from bond.config import get_default_persona
from bond.conversation.conversation import Conversation
from bond.conversation.types import UserConversationMessage, UserMessage
from bond.environment.std_async_event_handler import StdAsyncEventHandler
from bond.runtime import BondRuntime
from bond.tools.tool import ToolCallContext

from . import logger
from ._interactive import wait_for_turn_done


def _get_input_file_content(args: Namespace):
    if args.input_file:
        if_path = Path(args.input_file).expanduser().absolute()
        if not if_path.is_file():
            raise ValueError(f"Not a file: {args.input_file}")
        return if_path.read_text()
    if not os.isatty(sys.stdin.fileno()):
        return sys.stdin.read()
    return None


async def _run(args: Namespace):
    user_name = "User"

    request: str = args.first if args.second is None else args.second
    show_thoughts: bool = args.show_thoughts
    show_tool_output: bool = args.show_tool_output
    stream: bool = not args.no_stream if not show_thoughts else False
    no_save: bool = args.no_save
    if (input_file_content := _get_input_file_content(args)) is not None:
        request = input_file_content + "\n\n\n" + request
    is_interactive = not args.non_interactive

    # Setup environment
    env_path = Path("~/.config/bond").expanduser().absolute()
    conv_path = Path("~/.local/share/bond").expanduser().absolute()
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic(env_path, disable_local_config=args.disable_local_config)
    config = runtime.get_bond_config()

    persona_id: str = (
        get_default_persona(config.ask) if args.second is None else args.first
    )
    available_personas = runtime.list_personas()
    if persona_id not in available_personas:
        raise ValueError(
            f"not a valid persona: {persona_id}. "
            f"Available personas: {'\n'.join(available_personas)}"
        )
    persona_config_result = runtime.get_persona(persona_id)
    if isinstance(persona_config_result, Failure):
        print(persona_config_result.failure())
        return
    allow_shell = "shell" in persona_config_result.unwrap().toolsets

    # Setup conversation
    conversation = Conversation()

    event_loop = asyncio.get_event_loop()
    event_queue: asyncio.Queue[AsyncTurnEvent] = asyncio.Queue()
    tool_call_context = ToolCallContext.async_default(
        None, is_interactive, conversation, event_loop, event_queue
    )
    event_handler = StdAsyncEventHandler(
        event_queue,
        show_thoughts,
        show_tool_output,
        is_interactive,
        echo_user_message=False,
    )
    loop = AsyncAgentLoop(
        runtime,
        conversation,
        tool_call_context,
        event_queue,
        event_loop,
        persona_id,
        stream=stream,
        allow_shell_executions=allow_shell,
        save_after_turn=False,
        stop_on_failure=False,
    )

    event_handler.start(event_loop)
    try:
        await loop.start()
        user_message = UserConversationMessage(
            message=UserMessage.create(request), name=user_name
        )
        prompt_result = loop.prompt(user_message)
        if isinstance(prompt_result, Failure):
            print(prompt_result.failure(), file=sys.stderr)
            return
        # The loop becomes idle again once the prompt (including any tool call
        # follow-ups) has been fully processed.
        await wait_for_turn_done(loop)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Interrupted by user")
        await loop.cancel()
    finally:
        if loop.is_running:
            await loop.stop()
        # Let the event handler print everything that is still queued up
        await event_handler.drain()
        await event_handler.stop()

    if not no_save:
        conv_path.mkdir(parents=True, exist_ok=True)
        conversation.save_as("last-ask", conv_path)

    loop.persona.release()


def main():
    # Parse args
    parser = ArgumentParser("Ask Bond")
    parser.add_argument("first", type=str)
    parser.add_argument("second", type=str, nargs="?")
    parser.add_argument("--show-thoughts", action="store_true")
    parser.add_argument("--show-tool-output", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--input-file", "-i", type=str)
    parser.add_argument("--output-file", "-o", type=str)
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--disable-local-config",
        action="store_true",
        help="Ignore any local .bond directory (skills, scripts, conversations)",
    )

    args = parser.parse_args()
    util.setup_logger(args.debug, "ask.log")
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
