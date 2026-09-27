from pydantic import BaseModel


class BehaviourFlags(BaseModel):
    save_after_turn: bool = False
    save_on_quit: bool = False
    allow_shell_executions: bool = False
    stream: bool = False
