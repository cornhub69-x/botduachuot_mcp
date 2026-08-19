# Working Guide

## Recommended workflow

1. Call `duachuot_knowledge(section="overview")` to read the workspace, policy and document list.
2. Call `duachuot_knowledge(section="tools", query="<tool>")` before assuming a command is installed.
3. Use `duachuot_list_directory`, `duachuot_read_file` and `duachuot_search_text` to understand a project before modifying it.
4. Use `duachuot_check_command` for high-impact or hard-to-predict commands.
5. Modify files with `duachuot_write_file` or `duachuot_replace_in_file` where possible.
6. Run tests/lint with `duachuot_run_command` and report real evidence.

## Code modification rules

- Never overwrite existing changes without checking `git status` and `git diff`.
- Prefer small, tested, rollback-able changes.
- Never claim something is fixed without running the appropriate checks.
- Never write secrets, tokens or full sensitive commands into logs or docs.
- Use relative paths from `HOST_WORKSPACE_DIR` when possible.

## When running commands

- Set `cwd` to the correct project.
- Use a sensible timeout.
- Read `exit_code`, `stdout`, `stderr` and the `*_truncated` flags.
- If a command is blocked by policy, do not try to bypass it from the caller side; change the server-side config or pick a safer approach.
