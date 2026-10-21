from bond.capabilities.types import MessageListBuilder
from bond.providers.general.summarization import (
    DefaultSummarizationCapability,
    DefaultSummarizationOptions,
)
from bond.providers.mistral.chat_completions import MistralChatCompletions


class MistralSummarization(DefaultSummarizationCapability):
    def __init__(
        self,
        config: DefaultSummarizationOptions,
        chat_completions: MistralChatCompletions,
        message_list_builder: MessageListBuilder,
        cache_key: str | None,
    ):
        if cache_key is not None and config.thought_condensation is not None:
            if config.thought_condensation.model_options is None:
                config.thought_condensation.model_options = {}
            if "prompt_cache_key" not in config.thought_condensation.model_options:
                config.thought_condensation.model_options["prompt_cache_key"] = (
                    cache_key
                )
        super().__init__(config, chat_completions, message_list_builder)
