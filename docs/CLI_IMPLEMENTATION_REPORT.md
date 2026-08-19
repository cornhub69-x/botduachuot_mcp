# CLI Implementation Report

## Overview

The `duachuot` CLI has been fully implemented for the `botduachuot_mcp` repository following the Phase 1–5 plan.

Completion date: 2026-07-20.

Branch:

```text
refactor/host-core-clean-v1
```

## Added structure

```text
app/cli/
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
    ├── __init__.py
    ├── health.py
    ├── filesystem.py
    ├── command.py
    ├── knowledge.py
    ├── logs.py
    ├── config.py
    ├── doctor.py
    └── completion.py

bin/
└── duachuot

pyproject.toml
scripts/manual_test_cli.sh
docs/CLI_MANUAL_TEST_PLAN.md
```

## Command tree

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
├── config
├── doctor
├── completion
└── version
```

## Architecture

### Local operations

Lifecycle commands only wrap the official scripts:

```text
run_mcp_tunnel.sh
scripts/restart_server_only.sh
```

The CLI does not re-implement process management.

### API operations

Filesystem, command, knowledge, health and capabilities commands call the existing REST API.

The CLI does not re-implement:

- path boundaries;
- command policy;
- the file service;
- the command executor;
- the knowledge inventory;
- authentication.

### HTTP client

The REST client uses `urllib.request` from the standard library and supports:

- local URL;
- canonical public tunnel URL;
- custom base URL;
- bearer token;
- request timeout;
- JSON encode/decode;
- HTTP error mapping;
- command failure payloads even when REST returns HTTP 500.

## Exit-code semantics

```text
0  Success
1  Operation failed
2  Invalid arguments
3  Cannot reach the server
4  Authentication failed
5  Blocked by policy
6  Resource not found
7  Timeout
8  Conflict
```

`duachuot cmd run` preserves the real exit code of the command when the request was handled by the server.

## Packaging

Added:

```text
pyproject.toml
```

Console entry point:

```toml
[project.scripts]
duachuot = "app.cli.main:main"
```

Verified:

```text
.venv/bin/duachuot version
duachuot 1.0.0
```

`install_basic.sh` now installs dependencies and runs the editable install to create the entry point.

## Automated tests

Final result:

```text
37 passed in 8.44s
```

Includes the legacy tests and the new groups:

- parser;
- global option normalization;
- line ranges;
- output and secret redaction;
- REST client;
- auth/error mapping;
- non-zero command semantics;
- lifecycle helpers;
- CLI integration.

## Manual regression

Script:

```text
scripts/manual_test_cli.sh
```

Final result:

```text
TOTAL_PASS=18
ALL_CLI_MANUAL_TESTS=PASS
```

Groups that passed:

1. Build, executable, packaging, help, version.
2. Bash, Zsh and Fish completion.
3. Status, JSON and global option placement.
4. Local/public REST health.
5. Capabilities and filters.
6. Filesystem write sources.
7. File line ranges.
8. Append, replace, search, list and conflict.
9. Command policy.
10. Command execution semantics.
11. Knowledge sections.
12. Logs, grep, since and follow.
13. Config and token redaction.
14. Doctor local/public REST and MCP initialize.
15. Isolated lifecycle.
16. Live idempotent start.
17. Live server-only restart.
18. Pytest, compileall, Bash syntax and Git diff check.

## Isolated lifecycle

The full lifecycle was tested in a fake repository with a clean environment:

```text
ISOLATED_STATUS:
bridge=ready
ok=true
url=https://isolated-1.trycloudflare.com/mcp
workspace=/tmp/.../isolated-repo
```

Verified:

- start;
- idempotent start;
- status;
- server-only restart;
- stop;
- restart confirmation;
- full restart;
- new URL after full restart;
- no resurrected processes after stop.

## Real runtime

Before the final regression:

```text
Tunnel PID: 65323
URL: https://cambridge-plays-jessica-albums.trycloudflare.com/mcp
```

After `duachuot server restart`:

```text
Supervisor: running (65413)
Server:     running (106663)
Tunnel:     running (65323)
Bridge:     ready
URL:        https://cambridge-plays-jessica-albums.trycloudflare.com/mcp
```

Conclusion:

- server PID changed;
- tunnel PID unchanged;
- URL unchanged;
- local health pass;
- public REST pass;
- public MCP initialize pass.

A full tunnel restart was not run against the real runtime.

## Security behavior

The runtime keeps:

```text
REQUIRE_AUTH=false
```

As requested by the user, the CLI does not change this setting.

The CLI still supports tokens when auth is enabled later and always masks secrets in:

- `config show`;
- `config get`;
- JSON output;
- error details.

## Documentation

- `README.md` has a CLI usage section.
- `docs/CLI_DESIGN_PLAN.md` has the design and implementation status.
- `docs/CLI_MANUAL_TEST_PLAN.md` has the regression matrix.
- This file records the implementation and acceptance results.
