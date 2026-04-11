# TODO

- [-] Implement new command handler
- [x] Design new message structure (single block for modalities or list of entries)
- [x] Load messages on load (probably command handler's responsibility)
- [x] Make thoughts into folds
- [x] Make tool calls not separate messages, but folds like thoughts
- [x] Collapse Messages from iterative agent calls from the same turn into a single message
- [ ] Implement export in DefaultCommandHandler
- [ ] Implement statemachine
- [ ] Create interactive tool environment for tui
- [ ] Make crop and delete commands delete turns instead of messages to prevent invalid conversation states

## Bugs:

- [x] Conversation is not saved by tui because the command handler is responsible for it and the quit event is currently intercepted by the tui
- [x] Messages dont extend below the first line of text.
- [ ] Stop Event should be explicitly handled in waitforcommandresponse tui state as commands can quit the app
