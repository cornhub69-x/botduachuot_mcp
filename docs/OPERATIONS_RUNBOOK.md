# Operations Runbook

## 1. Installation

```bash
cd /home/light/GitHub/botduachuot_mcp
./scripts/install_basic.sh
```

The installer:

- creates or reuses `.venv`;
- installs pinned runtime dependencies;
- installs the editable `duachuot` package;
- creates the global `~/.local/bin/duachuot` symlink;
- creates `.env` when absent;
- applies mode `600` to `.env`;
- restores executable bits on CLI and shell scripts.

Verify:

```bash
duachuot version
duachuot config validate
```

## 2. Normal lifecycle

Start or adopt the managed supervisor:

```bash
duachuot start
```

Inspect status:

```bash
duachuot status
duachuot doctor
```

After ordinary Python/code changes, restart only the bridge:

```bash
duachuot server restart
```

This operation must preserve the tunnel PID and URL. Do not use `duachuot restart` for normal code changes.

Full restart, including a new Quick Tunnel URL:

```bash
duachuot restart --yes
```

Use only when the tunnel is dead, the URL is invalid, or a full restart is explicitly required.

## 3. Quality gates

Source and configuration gate:

```bash
./scripts/quality_gate.sh
```

Include local runtime checks:

```bash
./scripts/quality_gate.sh --runtime
```

Include public runtime and isolated lifecycle regression:

```bash
./scripts/quality_gate.sh --full
```

The legacy command remains an alias:

```bash
./scripts/test.sh
```

## 4. Doctor modes

Normal doctor allows warnings:

```bash
duachuot doctor
```

Offline/local-only diagnosis:

```bash
duachuot doctor --local-only
```

Strict production-style diagnosis treats warnings as failures:

```bash
duachuot doctor --strict
duachuot config validate --strict
```

`REQUIRE_AUTH=false` intentionally produces a warning. It is acceptable for the current development setup and should be enabled before production deployment.

## 5. Diagnostics collection

Create a redacted diagnostics directory:

```bash
./scripts/collect_diagnostics.sh
```

Choose a destination:

```bash
./scripts/collect_diagnostics.sh artifacts/support-case-001
```

The bundle excludes `.env` contents and runtime log bodies. It contains redacted configuration, status, doctor output, package metadata, and Git identity/state.

## 6. Recovery procedures

### Bridge is down but tunnel is alive

```bash
duachuot status
duachuot server restart
duachuot health
duachuot --public health
```

Confirm tunnel PID and URL remain unchanged.

### Stale PID file

Run:

```bash
duachuot config validate
duachuot doctor --local-only
```

Lifecycle scripts validate `/proc/<pid>/cmdline` before stopping a process. Unrelated reused PIDs are not terminated. Starting the supervisor removes/replaces stale managed state safely.

### Tunnel process is dead

```bash
duachuot status
duachuot start
```

The supervisor should recreate only the tunnel and publish the fresh canonical URL in `logs/tunnel_url.txt`.

### Port 8000 is occupied by an unrelated process

`duachuot server restart` refuses to terminate it. Identify the process manually:

```bash
lsof -nP -i :8000
```

Resolve the conflict explicitly; do not bypass the ownership check.

### Global `duachuot` command is missing

```bash
./scripts/install_cli.sh
rehash   # zsh
duachuot version
```

Remove only the repository-owned symlink:

```bash
./scripts/uninstall_cli.sh
```

## 7. Rollback

Before rollback, collect diagnostics and record the current tree:

```bash
./scripts/collect_diagnostics.sh artifacts/pre-rollback

git status --short
git diff --check
```

Restore only the intended files or commit. Do not reset unrelated user changes. After rollback:

```bash
./scripts/quality_gate.sh
duachuot server restart
duachuot doctor
```

A rollback of normal code must not restart the tunnel.

## 8. Logs and capacity

```bash
duachuot logs server -n 100
duachuot logs tunnel -n 100
duachuot logs audit -n 100
duachuot health --json
```

Health exposes:

- request/error/status counts;
- p50/p95 latency;
- in-flight and peak requests;
- active/queued/rejected command capacity;
- tracked rate-limit clients and capacity rejections.

Audit logs rotate according to:

```env
AUDIT_LOG_MAX_BYTES=10000000
AUDIT_LOG_BACKUP_COUNT=5
```

## 9. Production checklist

Before deployment:

1. Set `REQUIRE_AUTH=true`.
2. Generate and configure a fresh gateway token.
3. Keep `.env` mode `600`.
4. Run `duachuot config validate --strict`.
5. Run `./scripts/quality_gate.sh --full` against the authorized target.
6. Confirm no uncommitted or unreviewed changes.
7. Confirm capacity limits match the host resources.
8. Record rollback and recovery commands.
