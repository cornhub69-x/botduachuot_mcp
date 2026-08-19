# CLI Design Plan

## 1. Goals

Design a unified CLI for the `botduachuot_mcp` repository serving two needs:

1. Operate the local service, the server bridge and the Cloudflare Tunnel.
2. Call the Host MCP/REST capabilities from the terminal without hand-writing `curl`.

Proposed command name:

```text
duachuot
```

The CLI must prioritize:

- easy to remember;
- clear output;
- correct exit-code semantics;
- JSON support for scripting;
- no tunnel restart when only the server is changed or restarted;
- no breakage of the 12 MCP tools and the existing REST API;
- no extra layer of business logic independent of the core host service.

---

## 2. Design principles

### 2.1. One CLI, two execution modes

The CLI has two command groups:

#### Local operations

Run directly on the host machine and manage the process/runtime files:

```text
duachuot start
duachuot stop
duachuot restart
duachuot status
duachuot url
duachuot server restart
duachuot logs
duachuot config
```

#### API operations

Call the existing REST API:

```text
duachuot health
duachuot capabilities
duachuot fs ...
duachuot cmd ...
duachuot knowledge ...
```

By default the API mode calls the local server:

```text
http://127.0.0.1:8000
```

Switch to the current tunnel:

```text
duachuot --public health
```

Or point at a specific URL:

```text
duachuot --base-url https://example.trycloudflare.com health
```

### 2.2. No duplicated core logic

The CLI must not reimplement:

- path boundaries;
- file read/write/search;
- command policy;
- command execution;
- inventory;
- knowledge;
- authentication.

These must call back into the REST API or the official lifecycle scripts.

### 2.3. JSON-first but human-friendly

Every command supports:

```text
--json
```

Output is human-optimized by default. With `--json`, stdout contains only valid JSON for `jq` or CI scripts.

### 2.4. Meaningful exit codes

Proposal:

```text
0   Success
1   Operation failed
2   Invalid CLI arguments
3   Cannot reach the server
4   Authentication failed
5   Operation blocked by policy
6   Resource not found
7   Timeout
8   Conflict, e.g. file already exists
```

A command that ran successfully server-side but returned a non-zero exit code must keep the command's own semantics; it is not a server error.

---

## 3. Proposed command tree

```text
duachuot
├── start
├── stop
├── restart
├── status
├── url
├── server
│   ├── restart
│   └── status
├── health
├── capabilities
├── fs
│   ├── ls
│   ├── cat
│   ├── write
│   ├── append
│   ├── replace
│   ├── mkdir
│   └── search
├── cmd
│   ├── check
│   └── run
├── knowledge
│   ├── overview
│   ├── guide
│   ├── tools
│   ├── search
│   └── all
├── logs
│   ├── server
│   ├── tunnel
│   ├── launcher
│   ├── audit
│   └── follow
├── config
│   ├── show
│   ├── get
│   ├── path
│   └── validate
├── doctor
├── completion
│   ├── bash
│   ├── zsh
│   └── fish
└── version
```

---

## 4. Command group details

## 4.1. Lifecycle

### `duachuot start`

Equivalent to:

```bash
./run_mcp_tunnel.sh start
```

Requirements:

- idempotent;
- no second tunnel if the supervisor is already running;
- prints the URL as soon as Cloudflare provides it;
- does not wait for the bridge to be ready before printing the URL;
- does not read stale URLs from logs.

### `duachuot stop`

Equivalent to:

```bash
./run_mcp_tunnel.sh stop
```

Must stop the supervisor first, then the tunnel and the server.

### `duachuot restart`

Restarts supervisor/server/tunnel as a whole.

This command must clearly warn that the Quick Tunnel may receive a new URL.

Interactive confirmation is proposed:

```text
This may replace the current Cloudflare URL. Continue? [y/N]
```

Confirmation can be skipped with:

```text
--yes
```

### `duachuot server restart`

Equivalent to:

```bash
./scripts/restart_server_only.sh
```

This is the default command after routine code changes.

Requirements:

- no tunnel restart;
- check the tunnel PID before and after;
- warn if the tunnel PID changed unexpectedly;
- verify the bridge socket is ready.

### `duachuot status`

Proposed output:

```text
Supervisor  running   pid=65413
Server      running   pid=76445
Tunnel      running   pid=65323
Bridge      ready
URL         https://example.trycloudflare.com/mcp
Auth        disabled
Workspace   /home/light/GitHub
```

With `--json`:

```json
{
  "ok": true,
  "supervisor": {"running": true, "pid": 65413},
  "server": {"running": true, "pid": 76445},
  "tunnel": {"running": true, "pid": 65323},
  "bridge": "ready",
  "url": "https://example.trycloudflare.com/mcp",
  "auth_required": false,
  "workspace": "/home/light/GitHub"
}
```

---

## 4.2. Health and capabilities

### `duachuot health`

Calls:

```text
GET /api/v1/health
```

Human-readable output:

```text
Service       botduachuot-host-mcp
Version       1.0.0
Status        healthy
Uptime        12m 31s
Requests      120
Errors        0
Avg latency   1.2 ms
```

### `duachuot capabilities`

Calls:

```text
GET /api/v1/capabilities
```

Filterable:

```text
duachuot capabilities --tools
duachuot capabilities --limits
duachuot capabilities --host
```

---

## 4.3. File system

### `duachuot fs ls`

```bash
duachuot fs ls GitHub
duachuot fs ls GitHub --max 100
duachuot fs ls GitHub --json
```

Calls:

```text
GET /api/v1/files
```

### `duachuot fs cat`

```bash
duachuot fs cat GitHub/project/README.md
duachuot fs cat file.txt --lines 20:50
duachuot fs cat file.txt --max-bytes 100000
```

Calls:

```text
GET /api/v1/files/content
```

`--lines` convention:

```text
20:50
20:
:50
20
```

### `duachuot fs write`

Supports three content sources:

```bash
duachuot fs write path.txt --text "hello"
duachuot fs write path.txt --from local.txt
printf 'hello' | duachuot fs write path.txt --stdin
```

Flags:

```text
--no-overwrite
--no-create-parents
```

### `duachuot fs append`

```bash
duachuot fs append path.txt --text "next line"
printf 'next line' | duachuot fs append path.txt --stdin
```

### `duachuot fs replace`

```bash
duachuot fs replace path.txt --old "before" --new "after"
duachuot fs replace path.txt --old-file old.txt --new-file new.txt
duachuot fs replace path.txt --expected-count 1
```

### `duachuot fs mkdir`

```bash
duachuot fs mkdir project/data
duachuot fs mkdir project/data --no-parents
```

### `duachuot fs search`

```bash
duachuot fs search "FastMCP" --path GitHub/botduachuot_mcp
duachuot fs search "REQUIRE_AUTH" --case-sensitive --max 50
```

---

## 4.4. Command execution

### `duachuot cmd check`

```bash
duachuot cmd check 'git status --short'
```

Output:

```text
Allowed       yes
Policy        guarded
Commands      git
Severity      none
```

When blocked:

```text
Allowed       no
Rule          privilege_escalation
Message       Privilege escalation is blocked through MCP host tools.
```

### `duachuot cmd run`

```bash
duachuot cmd run 'git status --short' --cwd GitHub/botduachuot_mcp
duachuot cmd run --timeout 60 'pytest -q'
```

Output rules:

- command stdout goes to stdout;
- command stderr goes to stderr;
- metadata only printed with `--verbose`;
- `--json` returns the full response envelope;
- the CLI exit code mirrors the command's exit code when the request was handled successfully;
- server errors, policy blocks and timeouts use dedicated CLI exit codes.

Proposed addition:

```text
--check-first
```

to call the command-policy endpoint before executing.

---

## 4.5. Knowledge and inventory

### `duachuot knowledge overview`

```bash
duachuot knowledge overview
```

### `duachuot knowledge guide`

```bash
duachuot knowledge guide
duachuot knowledge guide --query docker
```

### `duachuot knowledge tools`

```bash
duachuot knowledge tools
duachuot knowledge tools --query python
duachuot knowledge tools --category security
duachuot knowledge tools --versions
duachuot knowledge tools --all
duachuot knowledge tools --uncatalogued
duachuot knowledge tools --refresh
```

### `duachuot knowledge search`

```bash
duachuot knowledge search docker
```

Searches guides and tool inventory at once.

---

## 4.6. Logs

```bash
duachuot logs server
duachuot logs tunnel
duachuot logs launcher
duachuot logs audit
duachuot logs follow server
duachuot logs follow --all
```

Flags:

```text
-n, --lines 100
-f, --follow
--since 10m
--grep ERROR
```

The CLI only reads local log files. No log deletion operation is provided by default.

---

## 4.7. Config

### `duachuot config show`

Shows only non-sensitive settings and masks secrets:

```text
MCP_BIND_HOST=127.0.0.1
MCP_PORT=8000
REQUIRE_AUTH=false
GATEWAY_TOKEN=********
HOST_WORKSPACE_DIR=/home/light/GitHub
HOST_COMMAND_POLICY=guarded
```

### `duachuot config get`

```bash
duachuot config get HOST_WORKSPACE_DIR
```

The real `GATEWAY_TOKEN` must never be printed unless an explicit flag says so, and by default such a flag should not exist.

### `duachuot config path`

```text
/home/light/GitHub/botduachuot_mcp/.env
```

### `duachuot config validate`

Checks:

- `.env` exists;
- port is valid;
- workspace exists;
- knowledge directory exists;
- command policy is valid;
- auth/token consistency;
- `cloudflared` exists when the tunnel is used;
- `.venv/bin/fastmcp` exists;
- PID file has no stale PID.

---

## 4.8. Doctor

```bash
duachuot doctor
```

Runs a non-destructive set of checks:

1. Python virtual environment.
2. `fastmcp` and `cloudflared`.
3. `.env` validation.
4. PID file.
5. Bridge socket.
6. Local `/healthz`.
7. Local REST health.
8. Public REST health when the tunnel is running.
9. MCP initialize when a URL exists.
10. Warn when auth is off on a public endpoint.

Output:

```text
PASS  virtualenv
PASS  fastmcp
PASS  cloudflared
PASS  config
PASS  bridge socket
PASS  local REST
PASS  public REST
PASS  MCP initialize
WARN  public endpoint has REQUIRE_AUTH=false
```

`doctor` never fixes the configuration and never restarts processes.

---

## 5. Global options

```text
--base-url URL
--public
--local
--token TOKEN
--token-file PATH
--timeout SECONDS
--json
--no-color
--verbose
--quiet
--version
-h, --help
```

Token resolution order:

1. `--token`.
2. `--token-file`.
3. `DUACHUOT_TOKEN`.
4. `GATEWAY_TOKEN` in the environment.
5. The repository `.env`.

Tokens must never appear in error messages, debug logs or CLI-generated command history.

---

## 6. Proposed code architecture

```text
app/
└── cli/
    ├── __init__.py
    ├── main.py
    ├── parser.py
    ├── context.py
    ├── client.py
    ├── output.py
    ├── errors.py
    ├── lifecycle.py
    ├── config_view.py
    └── commands/
        ├── health.py
        ├── filesystem.py
        ├── command.py
        ├── knowledge.py
        ├── logs.py
        ├── config.py
        └── doctor.py

bin/
└── duachuot

tests/
├── test_cli_parser.py
├── test_cli_output.py
├── test_cli_client.py
├── test_cli_lifecycle.py
└── test_cli_integration.py
```

### `app/cli/parser.py`

Uses `argparse` from the standard library to avoid an extra runtime dependency for the CLI.

### `app/cli/client.py`

REST client using `urllib.request` from the standard library.

Responsibilities:

- resolve base URL;
- add auth headers;
- encode queries;
- encode/decode JSON;
- timeout;
- map HTTP errors to CLI exceptions;
- no default retry for write operations.

### `app/cli/output.py`

Responsibilities:

- human-readable rendering;
- JSON rendering;
- stderr/stdout separation;
- color only when the terminal supports it;
- no color when piped or `NO_COLOR` is set.

### `app/cli/lifecycle.py`

Wraps only the official scripts:

```text
run_mcp_tunnel.sh
scripts/restart_server_only.sh
```

No process-management logic is copied into Python.

---

## 7. Packaging and executable

The repository currently has no `pyproject.toml`. Two deployment steps:

### Early stage

Create a wrapper:

```text
bin/duachuot
```

The wrapper calls:

```bash
exec "$ROOT_DIR/.venv/bin/python" -m app.cli.main "$@"
```

Users can run:

```bash
./bin/duachuot status
```

A local symlink can be created:

```bash
ln -s /home/light/GitHub/botduachuot_mcp/bin/duachuot ~/.local/bin/duachuot
```

### Packaging stage

Add `pyproject.toml` and the console entry point:

```toml
[project.scripts]
duachuot = "app.cli.main:main"
```

Then:

```bash
pip install -e .
```

Packaging is not required for the first CLI version.

---

## 8. UX and output conventions

### Success

```text
[+] Host MCP server restarted.
```

### Info

```text
[i] Tunnel was not restarted.
```

### Warning

```text
[!] Public endpoint is running without authentication.
```

### Error

```text
[-] Unable to connect to http://127.0.0.1:8000.
```

When stdout is piped, prefixes and colors may be dropped for easy parsing.

---

## 9. Testing plan

## 9.1. Unit tests

### Parser

- every command/subcommand;
- required arguments;
- aliases;
- conflicting flags;
- `--json`;
- `--public` and `--base-url`;
- line-range parser.

### REST client

- URL joining;
- query encoding;
- auth headers;
- JSON responses;
- invalid JSON;
- HTTP 400/401/403/404/408/409/429/500;
- network timeout;
- connection refused.

### Output

- human mode;
- JSON mode;
- secret redaction;
- command stdout/stderr;
- no-color mode.

### Lifecycle

- script mapping;
- server-only restart does not call tunnel restart;
- full restart requires confirmation;
- PID and URL checks.

## 9.2. Integration tests

Use the Starlette TestClient or an isolated local server:

- health;
- capabilities;
- fs lifecycle;
- command check/run;
- knowledge;
- auth enabled/disabled;
- exit-code mapping.

## 9.3. Manual regression

```text
PASS: duachuot status
PASS: duachuot health
PASS: duachuot --public health
PASS: duachuot fs ls
PASS: duachuot fs cat
PASS: duachuot fs write/append/replace/search
PASS: duachuot cmd check
PASS: duachuot cmd run success
PASS: duachuot cmd run non-zero exit
PASS: duachuot cmd run timeout
PASS: duachuot knowledge tools
PASS: duachuot logs server
PASS: duachuot config validate
PASS: duachuot doctor
PASS: duachuot server restart preserves tunnel PID and URL
PASS: duachuot start is idempotent
```

---

## 10. Implementation roadmap

### Phase 1 — Core CLI foundation

- `app/cli/main.py`;
- parser;
- context;
- REST client;
- error mapping;
- output formatter;
- `bin/duachuot`;
- `version`, `health`, `capabilities`.

### Phase 2 — Host operations

- `fs`;
- `cmd`;
- `knowledge`;
- tests for the API commands.

### Phase 3 — Lifecycle operations

- `start`;
- `stop`;
- `restart`;
- `status`;
- `url`;
- `server restart`;
- verify the tunnel survives a server restart.

### Phase 4 — Operations UX

- `logs`;
- `config`;
- `doctor`;
- shell completion;
- README examples.

### Phase 5 — Packaging

- `pyproject.toml`;
- editable install;
- version metadata;
- optional release artifact.

---

## 11. Acceptance criteria

The CLI counts as v1 complete when:

1. `duachuot --help` shows the full command tree.
2. `duachuot health` reaches the local REST API.
3. `duachuot --public health` uses the URL in `logs/tunnel_url.txt`.
4. `duachuot fs` covers the full file REST endpoints.
5. `duachuot cmd` preserves command exit-code semantics.
6. `duachuot knowledge` covers the current sections.
7. `duachuot server restart` does not change the tunnel PID or URL.
8. `duachuot restart` warns that the tunnel URL may change.
9. `duachuot status --json` returns valid JSON.
10. Tokens are always masked in output and logs.
11. All existing tests still pass.
12. New CLI tests pass.
13. Manual regression passes over local and public URLs.
14. No tunnel restart during routine development.

---

## 12. Out of v1 scope

Not implemented in CLI v1:

- interactive TUI;
- remote binary upload;
- websocket/SSE monitoring;
- automatic token rotation;
- automatic production deployment;
- complex multi-remote profile management;
- plugin system;
- automatic `.env` fixes without an explicit user command.

These may be considered for v2 once CLI v1 is stable.


---

## 13. Implementation status

Updated 2026-07-20: all of Phases 1–5 are implemented.

### Phase 1 — Core CLI foundation: DONE

- `app/cli/main.py`;
- parser and global option normalization;
- context/base URL/token resolution;
- REST client using the standard library;
- error mapping and exit codes;
- human/JSON output, color and secret redaction;
- `version`, `health`, `capabilities`;
- `bin/duachuot` executable.

### Phase 2 — Host operations: DONE

- all `fs` commands;
- `cmd check` and `cmd run`;
- command exit code preserved when REST maps command failure to HTTP 500;
- all `knowledge` sections;
- unit and integration tests.

### Phase 3 — Lifecycle operations: DONE

- `start`, `stop`, `restart`, `status`, `url`;
- `server restart` and `server status`;
- full restart requires confirmation or `--yes`;
- server-only restart verifies tunnel PID and URL before/after;
- status uses only the canonical URL file, never stale log URLs.

### Phase 4 — Operations UX: DONE

- logs: targets, tail, follow, grep, since and JSON;
- config: show, get, path and validate;
- doctor: local/public REST and MCP initialize;
- completion: Bash, Zsh and Fish;
- README examples;
- automated manual regression script.

### Phase 5 — Packaging: DONE

- `pyproject.toml`;
- `duachuot` console entry point;
- editable install;
- `install_basic.sh` installs the CLI automatically;
- `.gitignore` for packaging artifacts.

### Adjustments vs the original design

The global HTTP timeout is named:

```text
--request-timeout
```

instead of the global `--timeout`, to avoid clashing with:

```text
duachuot cmd run --timeout <command-timeout>
```

### Acceptance results

- pytest: `37 passed`;
- manual regression: `18/18 PASS`;
- marker: `ALL_CLI_MANUAL_TESTS=PASS`;
- real server-only restart keeps the tunnel PID and URL;
- full stop/restart was only run in an isolated environment;
- no real Cloudflare Tunnel restart during development.

See:

- `docs/CLI_MANUAL_TEST_PLAN.md`;
- `docs/CLI_IMPLEMENTATION_REPORT.md`;
- `scripts/manual_test_cli.sh`.
