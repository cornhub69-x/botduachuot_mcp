# BotDuaChuot Host MCP

MCP server tối giản để ChatGPT thao tác trực tiếp trên máy của bạn trong phạm vi `HOST_WORKSPACE_DIR`.

Repo này chỉ còn hai chức năng chính:

1. Đọc, ghi, tìm kiếm file và chạy command trên host.
2. Cung cấp hướng dẫn làm việc cùng danh mục tool thực tế có trong máy qua `duachuot_knowledge`.

## Cấu trúc

```text
app/
├── host/                 # Logic file, command, policy và tool inventory
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

## Cài đặt

### 1. One-line Install (khuyên dùng)

```bash
curl -fsSL https://raw.githubusercontent.com/cornhub69-x/botduachuot_mcp/main/install.sh | bash
```

Script mặc định clone nhánh `main` vào `~/.botduachuot_mcp`, tạo `.venv`, cài dependencies, tạo `.env` với quyền `600`, rồi liên kết CLI tại `~/.local/bin/duachuot`. Chạy lại cùng lệnh sẽ cập nhật installation bằng fast-forward; nếu working tree có file chưa commit, installer sẽ dừng để tránh ghi đè dữ liệu người dùng.

Có thể tùy chỉnh bằng biến môi trường:

```bash
curl -fsSL https://raw.githubusercontent.com/cornhub69-x/botduachuot_mcp/main/install.sh | \
  BQA_INSTALL_DIR="$HOME/apps/botduachuot_mcp" \
  BQA_BIN_DIR="$HOME/.local/bin" \
  BQA_BRANCH=main \
  bash
```

Các biến hỗ trợ: `BQA_REPO_URL`, `BQA_INSTALL_DIR`, `BQA_BIN_DIR`, `BQA_BRANCH`. `BQA_SKIP_PIP_UPGRADE=true` chỉ nên dùng trong môi trường kiểm thử hoặc offline đã chuẩn bị sẵn package cache.

### 2. Cài đặt thủ công từ repository local

```bash
cd botduachuot_mcp
./install.sh
```

`scripts/install_basic.sh` được giữ để tương thích và chuyển tiếp trực tiếp sang installer gốc.

### 3. Cấu hình và kiểm tra sau khi cài đặt

Đảm bảo `~/.local/bin` có trong `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Thêm dòng này vào `~/.bashrc` hoặc `~/.zshrc` để duy trì qua các session.

Cấu hình `.env` trước khi public service. Mặc định mẫu yêu cầu authentication:

```env
REQUIRE_AUTH=true
GATEWAY_TOKEN=<secret-random-token>
HOST_WORKSPACE_DIR=/home/user
```

Sau đó xác minh:

```bash
duachuot version
duachuot config validate
duachuot doctor
```


## Chạy qua Cloudflare Tunnel

```bash
./run_mcp_tunnel.sh
./run_mcp_tunnel.sh --status
./run_mcp_tunnel.sh --url
./run_mcp_tunnel.sh --stop
```

URL connector có dạng:

```text
https://<random>.trycloudflare.com/mcp
```

Streamable HTTP được cấu hình ở chế độ stateless và trả JSON trực tiếp. Mỗi request của ChatGPT hoạt động độc lập, không cần `mcp-session-id` và không giữ SSE stream cho các tool call thông thường.

```env
MCP_JSON_RESPONSE=true
MCP_STATELESS_HTTP=true
```

## REST API

REST API dùng chung host services với MCP và chạy trên cùng server/tunnel. Base path:

```text
/api/v1
```

OpenAPI document:

```text
/api/v1/openapi.json
```

Các endpoint chính:

| Method | Endpoint | Chức năng |
|---|---|---|
| `GET` | `/api/v1/health` | Trạng thái server |
| `GET` | `/api/v1/capabilities` | Tool, workspace và giới hạn |
| `GET` | `/api/v1/files` | Liệt kê thư mục |
| `GET` | `/api/v1/files/content` | Đọc file text |
| `PUT` | `/api/v1/files/content` | Tạo hoặc ghi đè file |
| `PATCH` | `/api/v1/files/content` | Thay thế text trong file |
| `POST` | `/api/v1/files/append` | Nối nội dung vào file |
| `POST` | `/api/v1/directories` | Tạo thư mục |
| `GET` | `/api/v1/search` | Tìm text trong workspace |
| `POST` | `/api/v1/commands/check` | Kiểm tra command |
| `POST` | `/api/v1/commands/run` | Chạy command trên host |
| `GET` | `/api/v1/knowledge` | Đọc guide và tool inventory |

Khi `REQUIRE_AUTH=true`, dùng một trong hai header:

```text
Authorization: Bearer <GATEWAY_TOKEN>
X-Gateway-Token: <GATEWAY_TOKEN>
```

Ví dụ:

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

## Tool MCP

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

`duachuot_run_command` không có tham số `approval="approved"`. Policy được quyết định hoàn toàn ở phía server.

## Investigation tools (Forensics + OSINT + Geo)

BotDuaChuot bổ sung 19 tool chuyên điều tra, chạy offline và deterministic:

```text
# Geo Engine (offline, không cần mạng)
duachuot_geo_extract         # EXIF GPS, cross-check exiftool/exiv2, DOP/HPE, timezone, landmarks
duachuot_coord_convert       # DMS/decimal/UTM/MGRS + datum transform (WGS84/ED50/NAD27)
duachuot_geo_calc            # geodesic distance/bearing + uncertainty từ DOP/HPE
duachuot_geo_reverse         # reverse geocoding offline (dataset landmarks.json)
duachuot_geo_verify          # >= 2 fact độc lập mới kết luận; thiếu fact -> BLOCKER
duachuot_geo_landmark_check  # kiểm tra bán kính quanh landmark
duachuot_timezone_at         # timezone/UTC offset offline từ tọa độ

# Probes
duachuot_media_probe         # file + exiftool JSON + ffprobe
duachuot_pcap_probe          # conversations/endpoints/DNS + GPS hints (NMEA, Wi-Fi probes)
duachuot_disk_probe          # fsstat + fls
duachuot_mem_probe           # Volatility 3 (info/pslist)
duachuot_stego_probe         # binwalk + steghide
duachuot_ocr_probe           # tesseract + QR (zxing-cpp)
duachuot_win_probe           # SAM/SYSTEM hive, LNK, prefetch (pure-Python, chạy trên Linux/Windows)

# OPSEC + platform
duachuot_ops_check           # chặn telemetry / attack tools / discovery khi ctf-live / flag trong lệnh
duachuot_ops_jitter          # delay giả lập người giữa các truy vấn mạng
duachuot_ops_redact          # redact secret/flag trước khi lưu log
duachuot_platform            # probe OS/arch/distro/shell + khả năng tool (native/WSL/missing)
duachuot_plan                # sinh kế hoạch điều tra theo loại artifact
```

Playbook đầy đủ: `knowledge/GEO_PLAYBOOK.md`, `knowledge/FORENSICS_PLAYBOOK.md`, `knowledge/OSINT_PLAYBOOK.md`. Skill đi kèm: `skills/ctf-geo`, `skills/ctf-forensics-plus`, `skills/ctf-osint-plus`, `skills/ctf-stego-plus`.

## OPSEC (bắt buộc khi thi CTF)

- Mặc định `ctf-live`: cấm truy vấn nguồn công khai (sherlock/maigret/whois/dnsrecon/search engine), cấm tool tấn công tự động vào scope, cấm submit flag tự động — luôn qua người dùng.
- Chế độ `investigation` (`OSINT_MODE=true`) mở các lookup OSINT đúng scope operator chỉ định.
- Giữa các truy vấn mạng: chờ `duachuot_ops_jitter()` (800–3000 ms).
- Mọi kết luận tọa độ cần >= 2 fact độc lập (kiểm qua `duachuot_geo_verify`).

## `duachuot_knowledge`

```text
duachuot_knowledge(section="overview")
duachuot_knowledge(section="guide")
duachuot_knowledge(section="tools", query="python", include_versions=true)
duachuot_knowledge(section="search", query="docker")
```

Tool này đọc tài liệu trong `knowledge/` và đối chiếu `TOOL_CATALOG.json` với `PATH` thực tế của máy.

## Kiểm thử

```bash
./scripts/test.sh
./scripts/quality_gate.sh
./scripts/manual_test_installer.sh
```

`manual_test_installer.sh` dùng repository và HOME tạm trong `/tmp`; nó không khởi động, dừng hoặc restart Cloudflare tunnel thật.

## Cấu hình quan trọng

```env
HOST_WORKSPACE_DIR=/home/light
HOST_RESTRICT_TO_WORKSPACE=true
HOST_COMMAND_POLICY=guarded
MAX_TIMEOUT_SECONDS=60
MAX_OUTPUT_BYTES=500000
REQUIRE_AUTH=true
GATEWAY_TOKEN=<secret>
```

`guarded` chỉ là lớp bảo vệ khỏi các thao tác phá máy rõ ràng, không phải sandbox. MCP server chạy với quyền của user khởi động process.

Xem thêm: `docs/ARCHITECTURE.md` và `SECURITY.md`.


## CLI `duachuot`

Repo có CLI thống nhất để vận hành bridge/tunnel và gọi REST API mà không cần viết `curl` thủ công.

Cài editable entry point:

```bash
.venv/bin/python -m pip install -e . --no-deps
```

Có thể chạy bằng một trong hai cách:

```bash
./bin/duachuot --help
.venv/bin/duachuot --help
```

Nhóm vận hành local:

```bash
duachuot start
duachuot status
duachuot url
duachuot server restart   # chỉ restart bridge, giữ nguyên tunnel URL
duachuot restart --yes    # restart cả tunnel, có thể đổi URL
duachuot stop
```

Nhóm REST API:

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

Các nhóm hỗ trợ vận hành:

```bash
duachuot logs server -n 100
duachuot logs follow server
duachuot config show
duachuot config validate
duachuot doctor
duachuot completion bash
```

Mọi lệnh đều hỗ trợ `--json`. Global options có thể đặt trước hoặc sau subcommand:

```bash
duachuot --public health --json
duachuot health --public --json
```

CLI mặc định gọi local REST tại `http://127.0.0.1:<MCP_PORT>`. Dùng `--public` để lấy URL hiện tại từ `logs/tunnel_url.txt`, hoặc `--base-url` để chỉ định endpoint khác.

Exit code chính:

```text
0  thành công
1  operation thất bại
2  sai tham số
3  không kết nối được server
4  authentication thất bại
5  policy chặn
6  resource không tồn tại
7  timeout
8  conflict
```

Riêng `duachuot cmd run`, khi server đã thực thi command thành công về mặt request, exit code CLI sẽ phản ánh exit code thật của command.

Thiết kế đầy đủ: `docs/CLI_DESIGN_PLAN.md`.

Tài liệu CLI bổ sung: `docs/CLI_MANUAL_TEST_PLAN.md` và `docs/CLI_IMPLEMENTATION_REPORT.md`.

## Vận hành và recovery

Quality gate thống nhất:

```bash
./scripts/quality_gate.sh
./scripts/quality_gate.sh --runtime
./scripts/quality_gate.sh --full
```

Doctor và config nghiêm ngặt:

```bash
duachuot doctor --local-only
duachuot doctor --strict
duachuot config validate --strict
```

Thu thập diagnostics đã che cấu hình nhạy cảm:

```bash
./scripts/collect_diagnostics.sh
```

Quy trình cài đặt, restart bridge không đổi tunnel, recovery, rollback và checklist production được mô tả tại `docs/OPERATIONS_RUNBOOK.md`.

## Kiến trúc, bảo mật và release

- Kiến trúc runtime và boundary: `docs/ARCHITECTURE.md`
- Mô hình bảo mật và hardening: `SECURITY.md`
- Vận hành, recovery và rollback: `docs/OPERATIONS_RUNBOOK.md`
- Checklist release: `docs/RELEASE_CHECKLIST.md`

GitHub Actions chạy quality gate trên push và pull request; Dependabot theo dõi Python và GitHub Actions dependencies.
