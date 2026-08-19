# Investigation Subsystem — BotDuaChuot

Tài liệu kỹ thuật cho khối điều tra (Forensics + OSINT + Geo) của BotDuaChuot:
`app/geo/`, `app/ops/`, `app/platform/`, các MCP tool `duachuot_*` mới, playbook
và skills. Bổ sung cho `ARCHITECTURE.md` (runtime) và `SECURITY.md` (bảo mật).

## 1. Geo Engine (`app/geo/`) — offline, deterministic

| Module | Trách nhiệm |
|---|---|
| `convert.py` | DMS ↔ decimal ↔ UTM ↔ MGRS; datum transform WGS84/ED50/NAD27/GRS80 (Helmert 7 tham số) |
| `geodesic.py` | Vincenty inverse + great-circle fallback; `uncertainty_from_dop` (HPE/DOP → bán kính sai số) |
| `exif_gps.py` | Trích GPS EXIF: exiftool (primary) + exiv2 (cross-check); 2 nguồn bất đồng → `None`, không merge yên lặng |
| `reverse.py` | Reverse geocoding offline theo `datasets/landmarks.json` (46 landmark, haversine + geodesic) |
| `timezone.py` | Bảng timezone offline (50+ zone) theo bbox |

Quyết định kỹ thuật đáng chú ý:

- **MGRS theo chuẩn NGA**: zone lẻ dùng set cột 8 ký tự trước, zone chẵn dùng set
  hàng 20 ký tự trước. Northing MGRS đo từ xích đạo cả 2 bán cầu (khác UTM nam:
  `utm_S = 10,000,000 - mgrs_northing`).
- **`from_mgrs` khử mơ hồ chu kỳ 2,000,000 m** bằng lat band: sinh 6 ứng viên
  (k=0..5) và chọn ứng viên nằm trong dải vĩ độ của band (tolerance 0.01° cho
  sai số truncation 5 chữ số) đồng thời nằm trong cửa sổ kinh tuyến trung tâm
  ±3.5° (loại output garbage của inverse UTM khi northing vượt cực). Band X là
  12° (72–84), các band khác 8°.
- **Round-trip đạt ≤4 m** trên 20 điểm kiểm thử phủ cả 2 bán cầu, cực, kinh tuyến
  đổi ngày, biên band. Bộ test: `tests/geo/test_geo_engine.py` (36 tests).

## 2. OPSEC Gate (`app/ops/gate.py`)

8 luật cứng (từ PLAN v2.0 mục 7). API:

- `gate_command(cmd, mode, dry_run)` — inspect lệnh local: chặn telemetry host
  (ip-api, api.ipify, geoip-db, ipinfo, shodan, censys...), chặn tool tấn công
  tự động (sqlmap, nmap, hydra, masscan, ffuf, metasploit...), chặn discovery
  công khai khi `ctf-live` (sherlock/maigret/whois/dnsrecon/search engine),
  chặn flag-like string trong lệnh.
- `gate_remote_request(target, mode, dry_run)` — cùng luật cho target mạng.
- `redact_secrets(text)` — redact flag/token/secret trước khi lưu log.
- `jitter_delay()` / `suggest_jitter_seconds()` — delay 800–3000 ms giữa các
  truy vấn mạng (giả lập người, cấm burst song song).

Mode mặc định `ctf-live` từ `app.config.OSINT_MODE` (False). Bật
`OSINT_MODE=true` chỉ khi operator xác nhận challenge cho phép lookup bên ngoài.

## 3. Platform Adapter (`app/platform/`)

- `probe_platform()` — OS/arch/distro (`/etc/os-release`)/shell/package managers,
  cache bằng `lru_cache`.
- `choose_executable(name)` — native PATH → (Windows) WSL bridge `wsl.exe which`.
- `tool_supported(name)` — báo cáo available/method (native|wsl|missing).
- `executor.py` dùng `_shell_invocation()`: bash `--noprofile --norc` trên
  Linux/macOS; WSL bridge, `powershell -NoProfile`, hoặc `cmd /d /s /c` trên
  Windows. Chiến lược: python-portable > native PATH > pkg-manager > WSL2.

## 4. MCP tools mới (19)

`app/tools/geo_tools.py` — `duachuot_geo_extract`, `duachuot_coord_convert`
(DMS/decimal/UTM/**MGRS** input), `duachuot_geo_calc`, `duachuot_geo_reverse`,
`duachuot_geo_verify` (≥2 fact độc lập → confidence; thiếu → BLOCKER),
`duachuot_geo_landmark_check`, `duachuot_timezone_at`.

`app/tools/probes.py` — `duachuot_media_probe` (file+exiftool+ffprobe),
`duachuot_pcap_probe` (tshark: conv/endpoints/DNS + GPS hints NMEA/Wi-Fi),
`duachuot_disk_probe` (fsstat+fls), `duachuot_mem_probe` (vol), `duachuot_stego_probe`
(binwalk+steghide), `duachuot_ocr_probe` (tesseract+QR zxing), `duachuot_win_probe`
(SAM/SYSTEM hive, LNK, prefetch — pure-Python).

`app/tools/ops_tools.py` — `duachuot_ops_check`, `duachuot_ops_jitter`,
`duachuot_ops_redact`, `duachuot_platform`, `duachuot_plan` (kế hoạch điều tra
theo loại artifact).

Nguyên tắc probe: tool thiếu → lỗi BLOCKER rõ ràng với tên lệnh cần cài; không
bao giờ đoán kết quả. Đăng ký trong `app/main.py`.

## 5. CLI (`duachuot`)

```
duachuot geo convert   [--lat --lon | --dms-lat --dms-lon | --utm-zone --easting --northing] [--datum-src --datum-dst]
duachuot geo reverse   LAT LON [--limit N]
duachuot geo verify    LAT LON
duachuot ops check     TARGET [--kind command|remote]
duachuot ops jitter
duachuot platform      [--tool NAME]
```

Cài: `bin/duachuot` (venv-aware). Thêm vào PATH hoặc `scripts/install_cli.sh`.

## 6. Kiểm thử

```bash
.venv/bin/python -m pytest tests/ -q                 # 54 tests
.venv/bin/python scripts/smoke_investigation.py      # MCP inventory + 7 functional checks
.venv/bin/python scripts/install_datasets.py         # validate datasets (offline)
```

## 7. Vận hành khi thi CTF

1. `duachuot platform --tool <tool>` — kiểm tra công cụ trước khi dùng.
2. Mọi lệnh/target mạng → `duachuot_ops_check` trước; chờ jitter giữa các bước.
3. Tọa độ: `geo_extract` → `coord_convert` → `geo_reverse` → `geo_verify` (≥2 fact).
4. Log phải qua `ops_redact`; flag chỉ hiển thị cho người, không tự submit.