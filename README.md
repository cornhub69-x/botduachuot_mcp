# BotDuaChuot Host MCP

A minimal MCP server that lets ChatGPT operate directly on your machine, scoped to `HOST_WORKSPACE_DIR`.

This repository has two main functions:

1. Read, write, search files and run commands on the host.
2. Provide working guidance plus a real inventory of tools installed on the machine via `duachuot_knowledge`.

## Layout

```text
app/
├── host/                 # File, command, policy and tool-inventory logic
├── geo/                  # Geo Engine (convert, geodesic, exif, reverse, timezone)
├── ops/                  # OPSEC gate
├── platform/             # OS/distro/arch/shell + tool resolution
├── tools/                # MCP adapters: health, host, knowledge, geo, probes, ops
├── config.py
├── mcp_server.py
└── main.py

knowledge/
├── WORKING_GUIDE.md
├── HOST_ENVIRONMENT.md
├── TOOL_CATALOG.json
├── GEO_PLAYBOOK.md
├── FORENSICS_PLAYBOOK.md
└── OSINT_PLAYBOOK.md

skills/
├── ctf-geo/
├── ctf-forensics-plus/
├── ctf-osint-plus/
└── ctf-stego-plus/

datasets/
└── landmarks.json

install.sh
scripts/
├── install_basic.sh
├── install_cli.sh
├── uninstall_cli.sh
├── restart_server_only.sh
├── start_tunnel_server.sh
├── dev.sh
├── install_datasets.py
└── test.sh
```

## Installation

### 1. One-line install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/cornhub69-x/botduachuot_mcp/main/install.sh | bash
```

By default the script clones the `main` branch into `~/.botduachuot_mcp`, creates a `.venv`, installs dependencies, creates a `.env` with `600` permissions, and links the CLI at `~/.local/bin/duachuot`. Re-running the same command updates the installation via fast-forward; if the working tree has uncommitted files, the installer stops to avoid overwriting user data.

It can be customized with environment variables:

```bash
curl -fsSL https://raw.githubusercontent.com/cornhub69-x/botduachuot_mcp/main/install.sh | \
  BQA_INSTALL_DIR="$HOME/apps/botduachuot_mcp" \
  BQA_BIN_DIR="$HOME/.local/bin" \
  BQA_BRANCH=main \
  bash
```

Supported variables: `BQA_REPO_URL`, `BQA_INSTALL_DIR`, `BQA_BIN_DIR`, `BQA_BRANCH`. `BQA_SKIP_PIP_UPGRADE=true` should only be used in test environments or offline setups with a prepared package cache.

### 2. Manual install from a local repository

```bash
cd botduachuot_mcp
./install.sh
```

`scripts/install_basic.sh` is kept for compatibility and forwards directly to the main installer.

### 3. Configuration and post-install checks

Make sure `~/.local/bin` is in your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add this line to `~/.bashrc` or `~/.zshrc` to keep it across sessions.

Configure `.env` before exposing the service. The default template requires authentication:

```env
REQUIRE_AUTH=true
GATEWAY_TOKEN=<secret-random-token>
HOST_WORKSPACE_DIR=/home/user
```

Then verify:

```bash
duachuot version
duachuot config validate
duachuot doctor
```


## Running through Cloudflare Tunnel

```bash
./run_mcp_tunnel.sh
./run_mcp_tunnel.sh --status
./run_mcp_tunnel.sh --url
./run_mcp_tunnel.sh --stop
```

The connector URL looks like:

```text
https://<random>.trycloudflare.com/mcp
```

Streamable HTTP is configured stateless and returns JSON directly. Every ChatGPT request works independently: no `mcp-session-id` is required and no SSE stream is kept for regular tool calls.

```env
MCP_JSON_RESPONSE=true
MCP_STATELESS_HTTP=true
```

## REST API

The REST API shares the host services with the MCP server and runs on the same server/tunnel. Base path:

```text
/api/v1
```

OpenAPI document:

```text
/api/v1/openapi.json
```

Main endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Server status |
| `GET` | `/api/v1/capabilities` | Tools, workspace and limits |
| `GET` | `/api/v1/files` | List directory |
| `GET` | `/api/v1/files/content` | Read text file |
| `PUT` | `/api/v1/files/content` | Create or overwrite file |
| `PATCH` | `/api/v1/files/content` | Replace text in file |
| `POST` | `/api/v1/files/append` | Append content to file |
| `POST` | `/api/v1/directories` | Create directory |
| `GET` | `/api/v1/search` | Search text in workspace |
| `POST` | `/api/v1/commands/check` | Check a command |
| `POST` | `/api/v1/commands/run` | Run a command on the host |
| `GET` | `/api/v1/knowledge` | Read guides and tool inventory |

When `REQUIRE_AUTH=true`, use one of these headers:

```text
Authorization: Bearer <GATEWAY_TOKEN>
X-Gateway-Token: <GATEWAY_TOKEN>
```

Example:

```bash
BASE_URL="https://<tunnel>.trycloudflare.com"
TOKEN="<GATEWAY_TOKEN>"

curl -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/api/v1/files?path=GitHub"

curl -X PUT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path":"Workspace/demo.txt","content":"hello REST\n"}' \
  "$BASE_URL/api/v1/files/content"

curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"git status --short","cwd":"GitHub/botduachuot_mcp"}' \
  "$BASE_URL/api/v1/commands/run"
```

## MCP tools

```text
health_check
get_capabilities
duachuot_list_directory
duachuot_read_file
duachuot_write_file
duachuot_replace_in_file
duachuot_append_file
duachuot_make_directory
duachuot_search_text
duachuot_check_command
duachuot_run_command
duachuot_knowledge
```

`duachuot_run_command` has no `approval="approved"` parameter. Policy is decided entirely server-side.

## Investigation tools (Forensics + OSINT + Geo)

BotDuaChuot adds 19 dedicated investigation tools, fully offline and deterministic:

```text
# Geo Engine (offline, no network required)
duachuot_geo_extract         # EXIF GPS, exiftool/exiv2 cross-check, DOP/HPE, timezone, landmarks
duachuot_coord_convert       # DMS/decimal/UTM/MGRS + datum transform (WGS84/ED50/NAD27)
duachuot_geo_calc            # geodesic distance/bearing + uncertainty from DOP/HPE
duachuot_geo_reverse         # offline reverse geocoding (landmarks.json dataset)
duachuot_geo_verify          # conclude only with >= 2 independent facts; fewer -> BLOCKER
duachuot_geo_landmark_check  # radius check around a landmark
duachuot_timezone_at         # offline timezone/UTC offset from coordinates

# Probes
duachuot_media_probe         # file + exiftool JSON + ffprobe
duachuot_pcap_probe          # conversations/endpoints/DNS + GPS hints (NMEA, Wi-Fi probes)
duachuot_disk_probe          # fsstat + fls
duachuot_mem_probe           # Volatility 3 (info/pslist)
duachuot_stego_probe         # binwalk + steghide
duachuot_ocr_probe           # tesseract + QR (zxing-cpp)
duachuot_win_probe           # SAM/SYSTEM hives, LNK, prefetch (pure-Python, Linux/Windows)

# OPSEC + platform
duachuot_ops_check           # blocks telemetry / attack tools / discovery while ctf-live / flags in commands
duachuot_ops_jitter          # human-like delay between network queries
duachuot_ops_redact          # redact secret/flag before writing logs
duachuot_platform            # probe OS/arch/distro/shell + tool availability (native/WSL/missing)
duachuot_plan                # generate an investigation plan by artifact type
```

Full playbooks: `knowledge/GEO_PLAYBOOK.md`, `knowledge/FORENSICS_PLAYBOOK.md`, `knowledge/OSINT_PLAYBOOK.md`. Bundled skills: `skills/ctf-geo`, `skills/ctf-forensics-plus`, `skills/ctf-osint-plus`, `skills/ctf-stego-plus`.

## OPSEC (mandatory during CTF)

- Default `ctf-live`: no public-source lookups (sherlock/maigret/whois/dnsrecon/search engines), no automated attack tools against scope, no automatic flag submission — always through a human.
- `investigation` mode (`OSINT_MODE=true`) opens OSINT lookups scoped to what the operator specifies.
- Between network queries: wait for `duachuot_ops_jitter()` (800–3000 ms).
- Every coordinate conclusion needs >= 2 independent facts (verified via `duachuot_geo_verify`).

## `duachuot_knowledge`

```text
duachuot_knowledge(section="overview")
duachuot_knowledge(section="guide")
duachuot_knowledge(section="tools", query="python", include_versions=true)
duachuot_knowledge(section="search", query="docker")
```

This tool reads the documents in `knowledge/` and matches `TOOL_CATALOG.json` against the machine's actual `PATH`.

## Testing

```bash
./scripts/test.sh
./scripts/quality_gate.sh
./scripts/manual_test_installer.sh
```

`manual_test_installer.sh` uses a temporary repository and HOME in `/tmp`; it never starts, stops or restarts a real Cloudflare tunnel.

## Key configuration

```env
HOST_WORKSPACE_DIR=/home/light
HOST_RESTRICT_TO_WORKSPACE=true
HOST_COMMAND_POLICY=guarded
MAX_TIMEOUT_SECONDS=60
MAX_OUTPUT_BYTES=500000
REQUIRE_AUTH=true
GATEWAY_TOKEN=<secret>
```

`guarded` is only a protection layer against obviously destructive operations, not a sandbox. The MCP server runs with the privileges of the user that starts the process.

See also: `docs/ARCHITECTURE.md` and `SECURITY.md`.


## `duachuot` CLI

The repository ships a unified CLI to operate the bridge/tunnel and call the REST API without hand-writing `curl`.

Install the editable entry point:

```bash
.venv/bin/python -m pip install -e . --no-deps
```

Run it either way:

```bash
./bin/duachuot --help
.venv/bin/duachuot --help
```

Local operations group:

```bash
duachuot start
duachuot status
duachuot url
duachuot server restart   # restart the bridge only, keep the tunnel URL
duachuot restart --yes    # restart the tunnel too, URL may change
duachuot stop
```

REST API group:

```bash
duachuot health
duachuot --public health
duachuot capabilities --tools
duachuot fs ls GitHub
duachuot fs cat GitHub/project/README.md --lines 1:40
duachuot fs write GitHub/demo.txt --text "hello"
printf 'next\n' | duachuot fs append GitHub/demo.txt --stdin
duachuot fs search FastMCP --path GitHub/botduachuot_mcp
duachuot cmd check 'git status --short'
duachuot cmd run 'git status --short' --cwd GitHub/botduachuot_mcp
duachuot knowledge tools --query python --versions
```

Operations support groups:

```bash
duachuot logs server -n 100
duachuot logs follow server
duachuot config show
duachuot config validate
duachuot doctor
duachuot completion bash
```

Every command supports `--json`. Global options can be placed before or after the subcommand:

```bash
duachuot --public health --json
duachuot health --public --json
```

By default the CLI calls the local REST endpoint at `http://127.0.0.1:<MCP_PORT>`. Use `--public` to take the current URL from `logs/tunnel_url.txt`, or `--base-url` to point at another endpoint.

Main exit codes:

```text
0  success
1  operation failed
2  invalid arguments
3  cannot reach the server
4  authentication failed
5  blocked by policy
6  resource not found
7  timeout
8  conflict
```

For `duachuot cmd run`, when the server executed the command successfully at the request level, the CLI exit code mirrors the real exit code of the command.

Full design: `docs/CLI_DESIGN_PLAN.md`.

Additional CLI docs: `docs/CLI_MANUAL_TEST_PLAN.md` and `docs/CLI_IMPLEMENTATION_REPORT.md`.

## Operations and recovery

Unified quality gate:

```bash
./scripts/quality_gate.sh
./scripts/quality_gate.sh --runtime
./scripts/quality_gate.sh --full
```

Strict doctor and config:

```bash
duachuot doctor --local-only
duachuot doctor --strict
duachuot config validate --strict
```

Collect diagnostics with sensitive configuration redacted:

```bash
./scripts/collect_diagnostics.sh
```

Installation, bridge-only restart (keeping the tunnel), recovery, rollback and the production checklist are described in `docs/OPERATIONS_RUNBOOK.md`.

## Architecture, security and releases

- Runtime architecture and boundaries: `docs/ARCHITECTURE.md`
- Security model and hardening: `SECURITY.md`
- Operations, recovery and rollback: `docs/OPERATIONS_RUNBOOK.md`
- Release checklist: `docs/RELEASE_CHECKLIST.md`

GitHub Actions runs the quality gate on push and pull request; Dependabot tracks Python and GitHub Actions dependencies.
