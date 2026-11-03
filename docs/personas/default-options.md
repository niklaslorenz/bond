# Default Options

Most capabilities come with a default implementation and some providers reuse their configuration.
To see which options a specific provider expects, view the [provider specific configuration](./index.md#list-of-available-providers).

## Generation

| Key           | Type           | Optional | Description                                                                         |
| ------------- | -------------- | -------- | ----------------------------------------------------------------------------------- |
| model         | str            | no       | The model id                                                                        |
| model_options | dict[str, Any] | yes      | Provider specific options that are passed directly to the chat completions endpoint |
| system_prompt | str            | yes      | The system prompt to use for generation tasks (supports macros)                     |

## Summarization

| Key                           | Type          | Optional | Description                                                                                                             |
| ----------------------------- | ------------- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
| token_threshold               | int           | no       | Token usage threshold that triggers a summarization                                                                     |
| keep_turns                    | int           | no       | Number of turns that are kept and are not summarized                                                                    |
| min_summarized_turns          | int           | no       | Number of turns that have to be available before summarization can be triggered (takes precedense over token_threshold) |
| summary_handler               | object        | no       | Configuration for the summarization process                                                                             |
| summary_handler.model         | str           | no       | The model id                                                                                                            |
| summary_handler.model_options | dict[str,Any] | yes      | Provider specific options that are passed directly to the chat completions endpoint                                     |
| summary_handler.prompt        | str           | no       | The system prompt for the summarization tasks (supports macros)                                                         |
| summary_handler.instruction   | str           | yes      | The user-level instruction that is appended to the summarization call's message list, if the strategy supports it       |
| summary_handler.chunk_size    | int           | yes      | The chunk size that the conversation is chunked into when summarizing, if the strategy supports it                      |
| task_list_handler             | object        | yes      | Configuration for updating the task list                                                                                |
| working_set_handler           | object        | yes      | Configuration for updating the working set                                                                              |

## Thought Condensation

| Key             | Type           | Optional | Description                                                                         |
| --------------- | -------------- | -------- | ----------------------------------------------------------------------------------- |
| model           | str            | no       | The model id                                                                        |
| model_options   | dict[str, Any] | yes      | Provider specific options that are passed directly to the chat completions endpoint |
| prompt          | str            | no       | System prompt for thought condensation tasks (supports macros)                      |
| token_threshold | int            | no       | Token usage threshold for a thought block that triggers a condensation run          |

## TTS

| Key   | Type | Optional | Description  |
| ----- | ---- | -------- | ------------ |
| model | str  | no       | The model id |
| voice | str  | no       | The voice id |

## Memory

| Key               | Type           | Optional | Description                                                                  |
| ----------------- | -------------- | -------- | ---------------------------------------------------------------------------- |
| model             | str            | no       | The model id                                                                 |
| vector_store      | str            | no       | The vector store name                                                        |
| vector_store_type | "faiss"        | yes      | The vector store implementation (currently only "faiss" is supported)        |
| embedding_options | dict[str, Any] | yes      | Provider specific options that are passed directly to the embedding endpoint |
