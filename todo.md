# Terminal AI Assistant: Project Summary

## **Purpose**
Build a **modular, terminal-based AI assistant** that integrates multiple AI
providers (Mistral, OpenAI, Ollama) and supports **configurable personas**
with custom behaviors, tools, and workflows.

### **Key Features**
- **Multi-Provider Support**: Use Mistral, OpenAI, or Ollama as the backend.
- **Configurable Personas**: Define personas with specific models, system prompts, tools, and behaviors (e.g., simple Q&A or multi-step agent loops).
- **Tool Integration**: Plug in tools like web search, code execution, and file I/O.
- **Structured Memory**: Track conversations hierarchically, preserving order for thoughts, tool calls, and responses.
- **Terminal Interface**: Interactive CLI for user-friendly interaction.

---

# Agent System Implementation Roadmap

## 1. Memory System
- [x] **Design and implement hierarchical memory** (done in `memory.py`).
- [ ] **Add context capping** to limit the number of turns/events sent to the model.
- [ ] **Add timestamps** to events for debugging and logging.
- [ ] **Extend for parallel tool calls** if needed.

## 2. Tool Integration
- [x] **Implement web search tool** (done in `web_search.py`).
- [ ] **Integrate tools with memory system**:
  - Append tool calls and responses to `ConversationMemory`.
  - Handle tool errors and retries.
- [ ] **Add more tools** (e.g., code interpreter, file I/O).

## 3. Persona System
- [x] **Define persona configs** (done in `persona_config.py`).
- [ ] **Load persona configs dynamically** from JSON/YAML files.
- [ ] **Integrate personas with memory and tools**:
  - Use persona configs to set system prompts, tools, and behavior.
  - Support switching personas at runtime.

## 4. Agent Loop
- [ ] **Implement simple agent loop** (single response):
  - Use `ConversationMemory` and `MistralAPI` for direct responses.
- [ ] **Implement multi-step agent loop**:
  - Use memory to chain thoughts, tool calls, and responses.
  - Handle parallel tool calls if needed.

## 5. Mistral API Integration
- [x] **Implement Mistral API wrapper** (done in `mistral.py`).
- [ ] **Add error handling and retries** for API calls.
- [ ] **Support streaming responses** if needed.

## 6. Terminal Interface
- [ ] **Implement CLI** for user interaction:
  - Use `argparse` or `click` for commands (e.g., `--persona code_assistant`).
  - Support interactive mode with conversation history.

## 7. Testing and Debugging
- [ ] **Write unit tests** for memory, tools, and agent loops.
- [ ] **Add logging** for debugging agent workflows.
- [ ] **Test edge cases** (e.g., empty queries, tool failures).

## 8. Documentation
- [ ] **Document the memory system** and its usage.
- [ ] **Document tool integration** and persona configs.
- [ ] **Write a README** for the project setup and usage.

## 9. Extensions (Optional)
- [ ] **Add support for multi-agent collaboration**.
- [ ] **Implement context summarization** for long conversations.
- [ ] **Add caching** for frequent tool calls or queries.

