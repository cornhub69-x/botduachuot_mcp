# Host Environment

## Runtime

- The MCP server runs directly with the user account that started the process.
- Files and commands are scoped by `HOST_WORKSPACE_DIR`.
- `HOST_RESTRICT_TO_WORKSPACE=true` should stay the default.
- `HOST_COMMAND_POLICY=guarded` blocks obviously destructive or privilege-escalating operations.
- This is not a sandbox; valid commands run with the privileges of the user that runs the server.

## Tool discovery

`duachuot_knowledge` matches `TOOL_CATALOG.json` against the actual `PATH` of the MCP process.

- `available=true` means the command was found in `PATH`.
- Versions are only probed with fixed arguments declared in the catalog.
- Use `refresh=true` to drop the cache and re-check.

## Current workspace

Check the actual configuration with:

```text
duachuot_knowledge(section="overview")
duachuot_get_capabilities
```
