from typing import TYPE_CHECKING

from bond.providers.general.thought_condensation import (
    DefaultThoughtCondensationCapability,
    DefaultThoughtCondensationOptions,
)
from bond.providers.mistral.chat_completions import MistralChatCompletions

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


class MistralThoughtCondensation(DefaultThoughtCondensationCapability):
    def __init__(
        self,
        config: DefaultThoughtCondensationOptions,
        chat_completions: MistralChatCompletions,
        cache_key: str,
        runtime: "BondRuntime | None" = None,
    ):
        if config.model_options is None:
            config.model_options = {}
        if "prompt_cache_key" not in config.model_options:
            config.model_options["prompt_cache_key"] = cache_key
        super().__init__(config, chat_completions, runtime)
