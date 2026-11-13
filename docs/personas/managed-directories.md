# Managed Directories

A persona can declare **managed directories** — folders outside the current working
directory that the agent can access directly, without asking for permission each time.

## Configuration

```yaml
# ~/.config/bond/personas/<persona>.yaml
name: my-persona
managed_directories:
  - name: sandbox
    path: ~/bond/managed_directories/sandbox   # read-write
  - name: archive
    path: ~/bond/managed_directories/archive
    read_only: true                            # reading only
```

Each entry has:

| Key         | Type   | Optional | Description                                              |
| ----------- | ------ | -------- | -------------------------------------------------------- |
| name        | str    | no       | URI prefix; must be unique and a single path segment     |
| path        | str    | no       | Real directory; `~` is expanded; must be unique          |
| read_only   | bool   | yes      | If `true`, write tools refuse to touch the directory     |

## Addressing files

Use the `bond://` URI scheme wherever a file tool takes a path:

```
bond://<name>/<path/to/file>
bond://<name>              # the root of the managed directory
```

All file tools accept these URIs: `read_file`, `list_directory`, `create_file`,
`apply_patch`, `remove_file`, `search_file`, `grep`, `tree`, `pdf_info`, `read_pdf_text`.

## Rules

- **Pre-authorized**: paths inside a managed directory never trigger an access
  confirmation, even when the current working directory is disabled (`cwd=None`).
- **Read-only**: `create_file`, `apply_patch` and `remove_file` fail with a
  permission error inside a `read_only` directory. Reading always works.
- **`.bond` / `.git` stay read-only**: write protection applies everywhere,
  including inside managed directories.
- **Lexical containment**: symlinks inside a managed directory are fine, but
  escapes like `bond://sandbox/../other` are rejected. Containment is checked
  lexically (no symlink resolution), so symlinked roots keep working.
- Unknown names (`bond://nope/...`) are an error; the valid names are listed in the
  `<managed-directories>` section of the system prompt.

## System prompt

The generation system-message builders include a `<managed-directories>` section
listing each directory's name, path and access mode (omitted when the persona
declares none). To teach the agent how to use the URIs, include the prompt snippet
`managed-directories.md` in the persona's `system_prompt` via a `{PROMPT:...}` macro.
