from bond.providers.general.thought_condensation import (
    DefaultThoughtCondensationCapability,
    DefaultThoughtCondensationOptions,
)
from bond.providers.mistral.chat_completions import MistralChatCompletions


class MistralThoughtCondensation(DefaultThoughtCondensationCapability):
    def __init__(
        self,
        config: DefaultThoughtCondensationOptions,
        chat_completions: MistralChatCompletions,
        cache_key: str,
    ):
        if config.model_options is None:
            config.model_options = {}
        if "prompt_cache_key" not in config.model_options:
            config.model_options["prompt_cache_key"] = cache_key
        super().__init__(config, chat_completions)
