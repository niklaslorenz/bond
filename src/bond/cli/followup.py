import os
from pathlib import Path

from bond.behaviours.loop import LoopBehaviour
from bond.bond_environment import DynamicBondEnvironment
from bond.config import BondConfig, get_default_persona
from bond.conversation.conversation import Conversation
from bond.default_command_handler import DefaultCommandHandler
from bond.io.stdenv import StdAoe, StdIoToolEnvironment, StdNotifier, StdSignalReceiver
from bond.tools import global_toolbox


def main():

    conv_path = Path("~/.local/share/bond").expanduser().absolute()
    env_path = Path("~/.config/bond/").expanduser().absolute()
    config_path = Path(env_path) / "config.json"
    config = BondConfig.load_from(config_path)

    env = DynamicBondEnvironment(
        env_path, global_toolbox.get_toolsets(config.chat.tools)
    )
    tool_environment = StdIoToolEnvironment(
        work_dir=lambda: Path(os.getcwd()), is_interactive=True
    )
    aoe = StdAoe()

    persona_name = get_default_persona(config.chat)
    last_ask_path = conv_path / "last-ask.json"
    last_conv_path = conv_path / "last-conv.json"
    conversation = (
        Conversation.model_validate_json(last_ask_path.read_text())
        if last_ask_path.is_file()
        else Conversation()
    )
    if len(conversation.history) == 0:
        print("<New Conversation>")
    else:
        print(f"<Loaded {len(conversation.history)} messages>")

    receiver = StdSignalReceiver(None)
    cmd_handler = DefaultCommandHandler(
        conversation_base_path=conv_path / "conversations",
        last_conv_path=last_conv_path,
        available_personas=config.chat.personas,
        save_on_quit=False,
    )
    loop = LoopBehaviour(
        conversation=conversation,
        environment=env,
        aoe=aoe,
        signal_receiver=receiver,
        notifier=StdNotifier(),
        command_handler=cmd_handler,
        tool_environment=tool_environment,
        persona_name=persona_name,
        stream=True,
        allow_shell_executions=True,
        user_name=config.user_name,
    )
    cmd_handler.link(loop)
    receiver.set_query(lambda: loop.persona_name)

    loop.run()


if __name__ == "__main__":
    main()
