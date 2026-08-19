# CLI Manual Regression Plan

## Goals

Verify all `duachuot` CLI logic after the Phase 1–5 implementation, including parser, packaging, local/public REST, filesystem, command execution, knowledge, logs, config, doctor, completion and lifecycle.

## Safety rules

- Never run `duachuot restart --yes` or `duachuot stop` against the real tunnel.
- The full `start/stop/restart` lifecycle is tested in an isolated repository with fake processes.
- The real runtime only runs `duachuot start` in idempotent mode and `duachuot server restart`.
- Before/after `duachuot server restart`, compare the tunnel PID and URL.
- Test files are created in a temporary directory under the repository and cleaned up afterwards.
- Never print the real `GATEWAY_TOKEN`.

## Test matrix

### A. Build and packaging

1. `compileall app/cli`.
2. `bash -n bin/duachuot`.
3. `pip install -e . --no-deps`.
4. `./bin/duachuot version`.
5. `.venv/bin/duachuot version`.
6. `duachuot --help` covers the command tree.

### B. Parser and output

1. Global options before the subcommand.
2. Global options after the subcommand.
3. `--json` produces valid JSON.
4. Line ranges: `N`, `N:M`, `N:`, `:M`.
5. Secrets in config are masked.
6. Usage errors exit with code `2`.

### C. Runtime status and health

1. `duachuot status`.
2. `duachuot status --json`.
3. `duachuot url`.
4. `duachuot server status`.
5. Local `duachuot health`.
6. Public `duachuot --public health`.
7. Full capabilities and the `--tools`, `--limits`, `--host` filters.

### D. Filesystem REST

1. `mkdir`.
2. `write --text`.
3. `write --from`.
4. `write --stdin`.
5. `cat` of a whole file.
6. `cat --lines` with all four range forms.
7. `append --text` and `append --stdin`.
8. `replace --old/--new`.
9. `replace --old-file/--new-file`.
10. `search`.
11. `ls`.
12. `--no-overwrite` returns conflict exit code `8`.

### E. Command REST

1. `cmd check` on a valid command.
2. `cmd check` on a policy-blocked command, exit code `5`.
3. Successful `cmd run`.
4. `cmd run` with `--check-first`.
5. `cmd run` with non-zero exit, CLI preserves the exit code.
6. `cmd run` timeout, CLI returns exit code `7`.
7. stdout and stderr are correctly separated.
8. Valid JSON envelope.

### F. Knowledge

1. `overview`.
2. `guide`.
3. `tools`.
4. `tools --versions`.
5. `tools --all`.
6. `search`.
7. `all`.

### G. Logs, config and diagnostics

1. The four log targets.
2. `--lines`.
3. `--grep`.
4. `--since`.
5. JSON logs.
6. Follow mode starts and is stopped with an external timeout.
7. `config show/get/path/validate`.
8. Token masking.
9. `doctor` local/public/MCP.
10. Completion for Bash, Zsh and Fish.

### H. Isolated lifecycle

1. `start` creates the fake supervisor/server/tunnel.
2. A second `start` is idempotent.
3. `status` reads the correct PIDs, bridge and canonical URL.
4. `server restart` changes the server PID but keeps the tunnel PID/URL.
5. `stop` stops the supervisor first and cleans up processes.
6. `restart --yes` runs the full lifecycle and issues a new URL in the fake environment.
7. `restart` without `--yes` is rejected in non-interactive mode.

### I. Real runtime

1. `duachuot start` does not change the tunnel PID/URL while the supervisor is running.
2. `duachuot server restart` only changes the server PID.
3. Tunnel PID and URL stay unchanged.
4. Local health, public REST and MCP initialize still pass after the bridge restart.

## PASS criteria

- All pytest automated tests pass.
- The manual regression script ends with `ALL_CLI_MANUAL_TESTS=PASS`.
- The real runtime keeps the tunnel PID and URL.
- No token appears in test artifacts/logs.
- `git diff --check`, `compileall` and `bash -n` pass.