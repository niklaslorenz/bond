from bond.conversation.conversation import MessageListBuilder
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
        generation_prompt: str | None,
        cache_key: str | None,
    ):
        if cache_key is not None and config.episode_summarization is not None:
            if config.episode_summarization.model_options is None:
                config.episode_summarization.model_options = {}
            if "prompt_cache_key" not in config.episode_summarization.model_options:
                config.episode_summarization.model_options["prompt_cache_key"] = (
                    cache_key
                )
        super().__init__(
            config, chat_completions, message_list_builder, generation_prompt
        )
