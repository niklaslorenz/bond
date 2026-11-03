# Ask Entrypoint

`ask` is a one-shot command line entry point for asking an agent a single question.
It is installed as the `ask` script (`bond.cli.ask:main`, source: `src/bond/cli/ask.py`).

## Usage

```bash
ask "What is the capital of France?"              # uses the default ask persona
ask my-persona "What is the capital of France?"   # uses a specific persona
cat notes.txt | ask "Summarize this"              # request is read from stdin
ask "Summarize this" -i notes.txt                 # file content is prepended to the request
```

The persona is chosen from the first positional argument if two arguments are given,
otherwise the `ask.default_persona` from `~/.config/bond/config.json` is used.
The request itself is the second positional argument (or the first, if no persona is given).
If stdin is not a terminal, its content is read and prepended to the request,
which makes `ask` usable in pipes.

## How it works

The endpoint is fully asynchronous and runs inside `asyncio.run(...)`:

1. The runtime is initialized from `~/.config/bond` and the requested persona is validated
   against the available personas and loaded.
2. A fresh `Conversation` is created and an `AsyncAgentLoop` (`src/bond/behaviours/async_loop.py`)
   is set up with an `asyncio.Queue` of turn events and a `ToolCallContext.async_default(...)`.
   Shell executions are allowed only if the persona's toolsets include `shell`.
3. The user message is handed to the loop via `loop.prompt(...)` and the loop is started.
   Because it is a loop (not a single turn), tool calls made by the model are executed
   automatically and the loop keeps going until the model produces a response without
   tool calls.
4. Events produced by the loop (response chunks, tool calls, errors, ...) are consumed by
   a `StdAsyncEventHandler` (`src/bond/environment/std_async_event_handler.py`) which prints
   them to stdout. The user message is *not* echoed for this endpoint
   (`echo_user_message=False`).
5. The endpoint waits until the loop's status returns to `Idle` (meaning the prompt and all
   tool call follow-ups have been fully processed), then stops the loop and the event
   handler, draining any remaining queued events first.
6. Unless `--no-save` is given, the conversation is saved as `last-ask` in
   `~/.local/share/bond` (`last-ask_metadata.json` + `last-ask_episodes.json`), so that the
   `followup` entry point can continue from it.

Logs are written to `~/.local/share/bond/logs/ask.log`.

## Options

| Flag                 | Description                                                                          |
| -------------------- | ------------------------------------------------------------------------------------ |
| `--show-thoughts`    | Print the model's thought blocks (disables streaming, since thoughts are streamed)   |
| `--show-tool-output` | Print the results of tool calls                                                      |
| `--non-interactive`  | Never ask for confirmation before running tools; confirmations are denied             |
| `-i`, `--input-file` | Read a file and prepend its content to the request                                   |
| `-o`, `--output-file`| (currently not implemented)                                                          |
| `--no-stream`        | Print the full response at once instead of streaming it                              |
| `--no-save`          | Do not save the conversation to `last-ask`                                           |
| `--debug`            | Enable debug logging                                                                 |
