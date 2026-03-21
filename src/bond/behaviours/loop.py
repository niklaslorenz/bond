from conversation import Conversation
from persona_config import PersonaConfig
from providers.mistral import MistralAPI


def loop_system_msg(persona_msg):
    return f"""
    You are an agent that works in a think-eval-resonse loop.
    You can lay out your thoughts by starting your message with "[THINK]".
    Whenever you do so, your response will not be visible to the user.
    Instead, you will be prompted again afterwards where you then can
    decide to continue with thoughts by using "[THINK]" again, or create
    a final answer that the user will see.
    
    This is how the user wishes you to act:
    {persona_msg}
    """


class LoopBehaviour:
    def __init__(self, api_key: str, persona: PersonaConfig):
        self.memory = Conversation.create(
            system_prompt=loop_system_msg(persona.system_prompt)
        )
        self.api = MistralAPI(api_key)
        self.persona = persona

    def process_turn(self, user_prompt: str) -> str:
        """Process a turn as a loop: thoughts, tool calls, and final response."""
        self.memory.add_user_message(user_prompt)

        while True:
            response = self.api.generate_response(
                model=self.persona.model, messages=self.memory.get_messages()
            )
            if response.strip().startswith("[THINK]"):
                self.memory.add_assistant_thought(response)
            else:
                self.memory.add_final_response(response)
                return response

    def __call__(self, user_prompt: str) -> str:
        return self.process_turn(user_prompt)
