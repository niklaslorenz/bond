import os
import threading
from pathlib import Path
from queue import Queue

from bond.behaviours.behaviour_signal import BehaviourSignal
from bond.behaviours.loop import LoopBehaviour
from bond.bond_environment import DynamicBondEnvironment
from bond.config import BondConfig, get_default_persona
from bond.conversation.conversation import Conversation
from bond.default_command_handler import DefaultCommandHandler
from bond.io.queue_env import (BehaviourEvent, QueueAoe, QueueNotifier,
                               QueueSignalReceiver, QueueToolEnvironment)
from bond.tools import global_toolbox
from bond.tui.app import BondTui


def main():
    signal_queue = Queue[BehaviourSignal]()
    event_queue = Queue[BehaviourEvent]()

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

    tool_env = QueueToolEnvironment(lambda: Path(os.getcwd()), event_queue)

    cmd_handler = DefaultCommandHandler(
        conversation_base_path=conversation_base_path,
        last_conv_path=last_conv_path,
        available_personas=config.chat.personas,
    )
    loop = LoopBehaviour(
        conversation=conversation,
        environment=env,
        aoe=QueueAoe(event_queue),
        signal_receiver=QueueSignalReceiver(signal_queue),
        notifier=QueueNotifier(event_queue),
        command_handler=cmd_handler,
        tool_environment=tool_env,
        persona_name=get_default_persona(config.chat),
        stream=True,
        allow_shell_executions=False,
        user_name=config.user_name,
    )
    cmd_handler.link(loop)

    thread = threading.Thread(target=loop.run, daemon=True)
    thread.start()
    app = BondTui(signal_queue, event_queue)
    app.run()


if __name__ == "__main__":
    main()
