from pathlib import Path

from bond.behaviours.loop import LoopBehaviour
from bond.config import BondConfig, get_default_persona
from bond.conversation.conversation import Conversation
from bond.environment.std_command_handler import StdCommandHandler
from bond.environment.std_event_handler import StdEventHandler
from bond.environment.std_signal_receiver import StdSignalReceiver
from bond.runtime import BondRuntime
from bond.tools.tool import ToolCallContext


def main():
    show_thoughts = False
    show_tool_output = False

    conv_path = Path("~/.local/share/bond").expanduser().absolute()
    env_path = Path("~/.config/bond/").expanduser().absolute()
    config_path = Path(env_path) / "config.json"
    config = BondConfig.load_from(config_path)

    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic(env_path)

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
    # TODO: Fix this persona mess. Get the default persona only if the conversation does not have one.
    # Also, why does loop update the persona multiple times during construction? Either take the one from the conversation
    # Or get the default yourself
    persona_id = get_default_persona(config.chat)
    tool_call_context = ToolCallContext.default(persona_id, True)

    receiver = StdSignalReceiver()
    event_handler = StdEventHandler(receiver, show_thoughts, show_tool_output)
    cmd_handler = StdCommandHandler(
        event_handler=event_handler,
        signal_handler=receiver,
        conversation_base_path=conv_path / "conversations",
        last_conv_path=last_conv_path,
        available_personas=config.chat.personas,
        save_on_quit=True,
        show_thoughts=show_thoughts,
    )
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
    receiver.link(lambda: loop.persona.name)
    cmd_handler.link(loop)

    loop.run()


if __name__ == "__main__":
    main()
