from typing import Any

from returns.result import Failure, Result, Success

from bond.conversation.conversation import Conversation
from bond.conversation.types import Message, SystemMessage, TextChunk, UserMessage
from bond.endpoints.chat_completions import ChatCompletionsEndpoint, CompletionResponse

from . import logger


class MistralConversationSummarizationStrategy:
    def __init__(
        self,
        model: str,
        model_options: dict[str, Any] | None,
        summarization_instruction: str,
        keep: int,
        max_retries: int,
        chat_completions: ChatCompletionsEndpoint,
        system_prompt: str | None = None,
    ):
        self._model = model
        self._model_options = model_options
        self._summarization_instruction = summarization_instruction
        self._keep = keep
        self._max_retries = max_retries
        self._chat_completions = chat_completions
        self._system_prompt = system_prompt

    def __call__(self, conversation: Conversation) -> Result[CompletionResponse, str]:
        logger.debug("Preparing summarization")
        messages, summary_index = self._extract_message_list(conversation)
        if summary_index < 0:
            return Failure(f"Summarization triggered with no messages to summarize")
        logger.debug(f"Summarizing {len(messages)} messages")

        if self._system_prompt is not None:
            messages = [SystemMessage(content=[TextChunk(text=self._system_prompt)])] + messages
        messages.append(
            UserMessage(content=[TextChunk(text=self._summarization_instruction)])
        )

        try:
            response = self._chat_completions.chat_completion(
                self._model,
                messages,
                [],
                None,
                self._model_options,
                self._max_retries,
            )
        except BaseException as e:
            return Failure(f"An error occured while creating summary ({type(e)}): {e}")

        summary_msg = response.choices[0].message
        if summary_msg.tool_calls:
            logger.warning(
                "Summary call returned with tool calls. This is not expected and the tool calls will be discarded."
            )
        if summary_msg.content is None:
            logger.error("Failed to create summary: no content")
            return Failure("Summary call returned without content")
        logger.debug(f"successfully created summary")

        summary = "".join(
            chunk.text for chunk in summary_msg.content if isinstance(chunk, TextChunk)
        )
        conversation.update_summary(summary, summary_index)
        logger.debug("Updated summary")
        return Success(response)

    def _extract_message_list(
        self, conversation: Conversation
    ) -> tuple[list[Message], int]:
        """
        Calculate the message list that should be used for summarization.
        Returns:
          list[Message]: messages to summarize
          int: The new summary_index for the conversation            
        """
        # Mistral's backend checks the following:
        # - A System Message MUST NOT appear outside of the first ever message
        # - Assistant Message MUST NOT follow another Assistant Message
        # - <n> Tool Messages MUST follow an Assistant message if, and only if,
        #   the Assistant Message has <n> tool calls
        # - After a block of Assistant Message and Tool Messages,
        #   a User Message or Assistant Message MAY follow
        # - The last message must not be an Assistant Message
        #
        # The message list that is passed to the summarization should fulfill the following:
        # - Preserve AT LEAST <self._keep> messages
        # - Include every message that is not kept and not already summarized
        # - Contain as few messages as possible, while adhering to the requirements above
        #   with a single exception: The last message of the extracted message list MAY be
        #   an Assistant Message, since the summarization prompt is injected as User Message
        # 
        if conversation.num_unsummarized_messages() <= self._keep:
            return [], -1

        # Find the next best lower cutoff.
        # The last message that is included just cannot have a Tool Message following it
        if self._keep != 0:
            lower_pivot = len(conversation.history) - self._keep # exclusive
            while lower_pivot > 0 and conversation.history[lower_pivot].message.role == "tool":
                lower_pivot -= 1
        else:
            lower_pivot = len(conversation.history)

        # Find the next best upper cutoff.
        # The first included message just cannot be a Tool Message
        upper_pivot = conversation.summary_index # inclusive
        while upper_pivot > 0 and conversation.history[upper_pivot].message.role == "tool":
            upper_pivot -= 1
        if upper_pivot != conversation.summary_index:
            logger.warning(f"Upper message pivot for summarization is misaligned. Included {conversation.summary_index - upper_pivot} additional previous messages in the summary")

        return [msg.message for msg in conversation.history[upper_pivot: lower_pivot]], lower_pivot
