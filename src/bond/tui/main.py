import os
import threading
from multiprocessing import Queue
from pathlib import Path

from bond.behaviours.loop import LoopBehaviour
from bond.bond_environment import DynamicBondEnvironment
from bond.config import BondConfig, get_default_persona
from bond.conversation.conversation import Conversation
from bond.tools import global_toolbox
from bond.tui.app import BondTui
from bond.tui.default_state_machine import DefaultTuiStateMachine
from bond.tui.environment.tui_command_handler import TuiCommandHandler
from bond.tui.environment.tui_signal_receiver import TuiSignalReceiver
from bond.tui.environment.tui_tool_environment import TuiToolEnvironment


def main():
    signal_queue = Queue()
    event_queue = Queue()

    config_base_path = Path("~/.config/bond").expanduser().absolute()
    data_base_path = Path("~/.local/share/bond").expanduser().absolute()
    conversation_base_path = data_base_path / "conversations"
    last_conv_path = data_base_path / "last-conv.json"

    config = BondConfig.load_from(config_base_path / "config.json")

    env = DynamicBondEnvironment(
        environment_path=config_base_path,
        tools=global_toolbox.get_toolsets(config.chat.tools),
    )

    conversation = (
        Conversation.model_validate_json(last_conv_path.read_text())
        if last_conv_path.is_file()
        else Conversation()
    )

    tool_env = TuiToolEnvironment(lambda: Path(os.getcwd()), event_queue)
    persona_id = get_default_persona(config.chat)
    persona = env.get_persona(persona_id)

    state_machine = DefaultTuiStateMachine(
        signal_queue=signal_queue,
        behaviour_event_queue=event_queue,
    )
    app = BondTui(persona, state_machine)
    state_machine.run(persona.name)

    cmd_handler = TuiCommandHandler(
        event_handler=state_machine.handle_behaviour_event,
        conversation_base_path=conversation_base_path,
        last_conv_path=last_conv_path,
        available_personas=config.chat.personas,
        save_on_quit=True,
    )
    loop = LoopBehaviour(
        conversation=conversation,
        environment=env,
        event_handler=state_machine.handle_behaviour_event,
        signal_receiver=TuiSignalReceiver(signal_queue),
        command_handler=cmd_handler,
        tool_environment=tool_env,
        persona_id=get_default_persona(config.chat),
        stream=True,
        allow_shell_executions=False,
        user_name=config.user_name,
        allowed_personas=config.chat.personas,
    )
    cmd_handler.link(loop)

    app.synchronize(conversation)
    thread = threading.Thread(target=loop.run, daemon=True)
    thread.start()
    app.run()


if __name__ == "__main__":
    main()
