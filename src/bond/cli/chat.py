import os
import sys
from pathlib import Path

from bond.behaviours.loop import LoopBehaviour
from bond.bond_environment import DynamicBondEnvironment
from bond.config import BondConfig, get_default_persona
from bond.conversation.conversation import Conversation
from bond.io.agent_output_environment import AgentOutputEnvironment
from bond.io.stream import WritethroughWrapper
from bond.repl import Repl
from bond.tools import global_toolbox
from bond.tools.tool import BidirectionalTextIO, ToolEnvironment


def main():

    user_io = BidirectionalTextIO(sys.stdin, WritethroughWrapper(sys.stdout))

    conv_path = Path("~/.local/share/bond").expanduser().absolute()
    env_path = Path("~/.config/bond/").expanduser().absolute()
    config_path = Path(env_path) / "config.json"
    config = BondConfig.load_from(config_path)
    env = DynamicBondEnvironment(
        env_path, global_toolbox.get_toolsets(config.chat.tools)
    )
    tool_environment = ToolEnvironment(
        interaction_io=user_io,
        tool_in=None,
        tool_out=None,
        work_dir=lambda: Path(os.getcwd()),
        shell_out=sys.stdout,
        shell_in=sys.stdin,
    )
    aoe = AgentOutputEnvironment(WritethroughWrapper(sys.stdout), None)
    persona_name = get_default_persona(config.chat)

    last_conv_path = conv_path / "last-conv.json"
    conversation = (
        Conversation.model_validate_json(last_conv_path.read_text())
        if last_conv_path.is_file()
        else Conversation()
    )
    if len(conversation.history) == 0:
        print("<New Conversation>")
    else:
        print(f"<Loaded {len(conversation.history)} messages>")

    loop = LoopBehaviour(
        environment=env,
        aoe=aoe,
        user_io=user_io,
        tool_environment=tool_environment,
        persona_name=persona_name,
        stream=True,
        allow_shell_executions=True,
        command_handler=None,
        user_name=config.user_name,
    )

    repl = Repl(
        loop,
        conversation,
        conv_path,
        last_conv_path,
        user_io,
        config.chat.personas,
        True,
    )

    repl.run()


if __name__ == "__main__":
    main()
