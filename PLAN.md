# BOT DƯA CHUỘT (BotDuachuot) — PLAN TOÀN CẢNH

> MCP bot thừa hưởng nền tảng BotQuangAnh, chuyên sâu **Forensics + OSINT**,
> tối ưu **tận dụng tool** và **xác định tọa độ chính xác**.
> Không bị coi là AI agent khi thi đấu (kiến trúc vô hình như BotQuangAnh).
> Chạy được trên **mọi Linux arch/distro + Windows**.
> Ngày: 2026-08-19 · Phiên bản: 2.0 (hoàn chỉnh)

---

## MỤC LỤC

1. Tầm nhìn & 5 nguyên tắc thiết kế
2. SƠ ĐỒ KIẾN TRÚC TỔNG THỂ
3. SƠ ĐỒ HOẠT ĐỘNG (flow điều tra 1 bằng chứng)
4. Thừa hưởng từ BotQuangAnh
5. Cấu trúc thư mục
6. Geo Engine — "tọa độ chính xác"
7. Tool Matrix & Resource Registry (kho ctf-tools)
8. Chính sách 2 chế độ (ctf-live / investigation)
9. Chống phát hiện — kiến trúc vô hình
10. Cross-platform (Linux mọi arch + Windows)
11. Danh sách tool MCP đầy đủ
12. Lộ trình (M1–M6)
13. Definition of Done
14. Rủi ro & giảm thiểu
15. Tính năng đề xuất (P0/P1/loại bỏ)

---

## 1. TẦM NHÌN & 5 NGUYÊN TẮC

BotDuaChuot = "trợ lý điều tra số" (không phải bot giải CTF đa năng):
trích xuất bằng chứng từ ảnh/video/audio/PCAP/disk/memory → xác định
**tọa độ chính xác** → cross-check ≥2 fact độc lập → kết luận kèm confidence.

**5 nguyên tắc thiết kế:**

| # | Nguyên tắc | Ý nghĩa |
|---|---|---|
| P1 | **Kiến trúc vô hình** | MCP local như BotQuangAnh: server CTF không bao giờ thấy bot, chỉ thấy request của user |
| P2 | **Evidence-first** | FACT/INFERENCE/HYPOTHESIS/BLOCKER trong solve_log.md; ≥2 fact độc lập mới kết luận |
| P3 | **Offline deterministic** | Geo Engine chạy offline, round-trip byte-for-byte; không phụ thuộc dịch vụ online khi thi |
| P4 | **Cross-platform** | Python thuần cho lõi + Platform Adapter cho tool; chạy được Linux mọi arch + Windows |
| P5 | **Tool-first** | Mọi tool trong kho ctf-tools là tài nguyên được quản lý (Resource Registry), probe version thật |

---

## 2. SƠ ĐỒ KIẾN TRÚC TỔNG THỂ

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    NGƯỜI DÙNG (human-in-the-loop)                        │
│   duyệt từng bước lớn · tự submit flag · điều khiển qua ChatGPT/opencode  │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ MCP streamable HTTP (stateless JSON)
                                │ Cloudflare Tunnel (chỉ operator, auth bắt buộc)
┌───────────────────────────────▼──────────────────────────────────────────┐
│                      botduachuot_mcp — MCP SERVER                        │
│                                                                          │
│  ┌─────────────────────────────┐   ┌───────────────────────────────────┐ │
│  │  CORE (kế thừa BotQuangAnh) │   │  INVESTIGATION TOOLS (mới)        │ │
│  │  health · capabilities      │   │  media_probe   (ảnh/audio/video)  │ │
│  │  fs_* (read/write/search)   │   │  pcap_probe    (flow + geo hints) │ │
│  │  run/check_command          │   │  disk_probe    (fls/fsstat+carve) │ │
│  │  knowledge · inventory      │   │  mem_probe     (vol3)             │ │
│  └─────────────────────────────┘   │  stego_probe   (LSB/carrier)      │ │
│  ┌─────────────────────────────┐   │  ocr_probe     (tesseract+QR)     │ │
│  │  GEO TOOLS (mới)            │   │  win_probe     (hives/MFT/LNK)    │ │
│  │  geo_extract · coord_convert│   └───────────────────────────────────┘ │
│  │  geo_calc · geo_reverse     │   ┌───────────────────────────────────┐ │
│  │  geo_verify · timezone_at   │   │  OPSEC GATE (mọi request)         │ │
│  └─────────────────────────────┘   │  local-first · jitter 0.8–3s      │ │
│                                    │  dry_run preview · zero telemetry │ │
│  ┌─────────────────────────────┐   │  human-submit · log sạch          │ │
│  │  GEO ENGINE (offline)       │   └───────────────────────────────────┘ │
│  │  EXIF GPS → DMS/decimal/    │   ┌───────────────────────────────────┐ │
│  │  UTM/MGRS → datum → geodesic│   │  RESOURCE REGISTRY                │ │
│  │  → heading → uncertainty    │   │  RESOURCE_MAP.json ← kho ctf-tools│ │
│  │  → landmark → confidence    │   │  (14 skill, scripts, venv, tools) │ │
│  └─────────────────────────────┘   └───────────────────────────────────┘ │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  PLATFORM ADAPTER  (os: linux/win/darwin · distro · arch · shell)  │ │
│  │  python-portable → native PATH → pkg-mgr (apt/dnf/pacman/winget)   │ │
│  │  → WSL2 (Windows) → container (arch hiếm)                          │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────────┐
│                  SKILLS  (skills/ + kế thừa ctf-tools/skills)            │
│  MỚI: ctf-forensics-plus · ctf-osint-plus · ctf-stego-plus · ctf-geo     │
│  KẾ THỪA: solve-challenge · ctf-writeup · ctf-pattern-archive · policy   │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ PATH thật (probe version)
┌───────────────────────────────▼──────────────────────────────────────────┐
│   HOST TOOL CHAIN  (Tool Matrix cấp A/B/C)                               │
│   A-có sẵn: exiftool exiv2 identify convert ffmpeg tshark tcpdump        │
│             binwalk foremost steghide fls fsstat vol strings yara        │
│   B-venv:   geographiclib piexif zxing-cpp pytesseract pymap3d z3        │
│   C-data:   tz database · landmark db · ellipsoid params                 │
└──────────────────────────────────────────────────────────────────────────┘

═══ BIÊN GIỚI CHALLENGE ═══════════════════════════════════════════════════
Server CTF chỉ thấy: HTTP request từ IP/máy user (không MCP, không AI,
không telemetry, không scan) ───────────────► challenge instance
```

---

## 3. SƠ ĐỒ HOẠT ĐỘNG (flow điều tra 1 bằng chứng)

```
Bằng chứng (ảnh/video/pcap/disk/mem)
        │
        ▼
[1] TRIAGE         file · magic · exiftool -json · solve_log.md cũ
        │
        ▼
[2] PROBE          media_probe / pcap_probe / disk_probe / mem_probe / stego_probe
        │            → chạy song song các tool A (chéo hóa exiftool+exiv2)
        ▼
[3] GEO EXTRACT    GPS thô → normalize → datum → WGS84 decimal
        │            (mọi nguồn: EXIF, QR/barcode, text OCR, landmark hint)
        ▼
[4] GEO CALC       distance/bearing/heading (GPSImgDirection) → uncertainty (DOP)
        │
        ▼
[5] GEO REVERSE    offline landmark match + timezone_at
        │
        ▼
[6] GEO VERIFY     ≥2 fact độc lập? ── không ──► BLOCKER (báo rõ, không đoán)
        │              │ có
        ▼              ▼
[7] KẾT LUẬN       {lat, lon, datum, accuracy_m, heading, timezone,
                    matches[], confidence 0–1 + lý do}
        │
        ▼
[8] HANDOFF        solve_log.md → writeup → NGƯỜI duyệt & submit flag
```

---

## 4. THỪA HƯỞNG TỪ BOTQUANGANH

| Thành phần | Nguồn | Cách dùng |
|---|---|---|
| `app/` (host, tools, mcp_server, rest_api, auth, policy) | `mcp/botquanganh_mcp/app/` | Fork, đổi prefix `duachuot_*` |
| `knowledge/` (WORKING_GUIDE, HOST_ENVIRONMENT, TOOL_CATALOG) | như trên | Mở rộng catalog 80+ tool |
| Policy `guarded` + auth + tunnel + rate limit | như trên | Giữ nguyên |
| Skill `solve-challenge`, `ctf-writeup` | `ctf-tools/skills/` | Giữ, thêm route geo |
| Sandbox `run_untrusted.py` (bwrap, netns riêng) | `ctf-pattern-archive/scripts/` | Bắt buộc cho artifact lạ |
| Vòng lặp evidence-first + verify | `ctf-resource-policy.md` | Fork thành policy 2 chế độ (§8) |
| Pattern archive (scripts + sqlite rỗng) | `ctf-pattern-archive/` | Giữ cơ chế; sẽ lấp dần sau mỗi event |

---

## 5. CẤU TRÚC THƯ MỤC

```
botduachuot_mcp/
├── app/
│   ├── host/          # files, executor (shell-aware), policy, inventory
│   ├── tools/         # MCP adapters: core + 10 investigation tools
│   ├── geo/           # GEO ENGINE (thuần python, offline)
│   │   ├── exif_gps.py    # parse mọi biến thể EXIF GPS (rational, DMS, datum)
│   │   ├── convert.py     # DMS↔decimal↔UTM↔MGRS, datum transform
│   │   ├── geodesic.py    # distance/bearing/uncertainty (geographiclib)
│   │   ├── reverse.py     # reverse-geocoding offline (dataset local)
│   │   └── timezone.py    # lat/lon → timezone (tz database local)
│   ├── ops/           # OPSEC GATE (jitter, dry_run, zero-telemetry check)
│   ├── platform/      # PLATFORM ADAPTER (probe os/distro/arch/shell + resolver)
│   ├── mcp_server.py  # + rest_api.py + config.py
├── knowledge/
│   ├── WORKING_GUIDE.md · HOST_ENVIRONMENT.md · TOOL_CATALOG.json
│   ├── FORENSICS_PLAYBOOK.md · OSINT_PLAYBOOK.md · GEO_PLAYBOOK.md
├── skills/            # ctf-forensics-plus, ctf-osint-plus, ctf-stego-plus, ctf-geo
│                       + symlink tới ctf-tools/skills (kế thừa)
├── datasets/          # timezone map · landmark db · ellipsoid params (offline)
├── resources/         # RESOURCE_MAP.json (sinh từ kho ctf-tools khi install)
├── scripts/           # install, tunnel, dev, test, quality_gate
├── tests/             # geo round-trip, platform, ops, policy
└── .env · README.md · SECURITY.md
```

---

## 6. GEO ENGINE — "TỌA ĐỘ CHÍNH XÁC"

Pipeline chuẩn:

```
1. geo_extract   exiftool -json -GPS* + exiv2 (chéo hóa) → GPS thô
2. normalize     DMS "51°30'26.5\"N" | rational | decimal | UTM | MGRS → WGS84
                 └ datum gốc ghi rõ (WGS84/ED50/NAD27/GRS80)
3. refine        GPSImgDirection → vector "đứng A, nhìn B"
                 GPSAltitude · GPSDOP (độ chính xác) · GPSDateTime (đối chiếu tz)
4. geo_calc      geodesic distance/bearing A→B · uncertainty = f(DOP)
5. geo_reverse   landmark match offline (dataset local)
6. geo_verify    ≥2 fact độc lập (EXIF + landmark + timezone + hướng)
                 └ <2 fact → BLOCKER
                 └ output: {lat, lon, datum, accuracy_m, heading,
                            timezone, matches[], confidence}
```

**Quy tắc vàng**: mọi chuyển đổi phải round-trip byte-for-byte
(decimal→DMS→decimal); cấm reverse-geo online khi ctf-live; datum cũ
(NAD27/ED50) ghi chú độ lệch ~100–500m.

---

## 7. TOOL MATRIX & RESOURCE REGISTRY

### 7.1 Tool Matrix 3 cấp

| Cấp | Định nghĩa | Danh sách |
|---|---|---|
| **A — có sẵn** | PATH thật, probe version | exiftool exiv2 identify convert ffmpeg ffprobe tshark tcpdump binwalk foremost steghide fls fsstat vol strings yara tesseract file xxd |
| **B — cần cài** | vào CTF venv | geographiclib piexif zxing-cpp pytesseract pymap3d numpy PIL |
| **C — data offline** | nhúng datasets/ | tz database · natural-earth landmarks · ellipsoid params · country/state polygons |

### 7.2 Resource Registry (kho ctf-tools = tài nguyên quản lý)

| Nguồn | Dùng cho |
|---|---|
| `skills/*` (14 skill) | routing + playbook |
| `skills/*/scripts` (crypto_triage, apk_triage, run_sage, model_triage, run_untrusted, pattern-archive 5 scripts) | gọi trực tiếp qua registry |
| `tools/RsaCtfTool` | crypto attack cụ thể (có evidence) |
| `tools/pentestcode` | CHỈ chế độ investigation, user chủ động |
| `bin/ctfpy` + venv `~/CTF/tools/venv` | runtime mặc định |
| `notes/CTF-KNOWLEDGE.md` | seed knowledge base |

`RESOURCE_MAP.json` (sinh khi install): path + category + invoke template +
platform yêu cầu. Thiếu resource → BLOCKER, không chạy sai.

---

## 8. CHÍNH SÁCH 2 CHẾ ĐỘ

| | **ctf-live** (mặc định) | **investigation** (`OSINT_MODE=on`) |
|---|---|---|
| Web search / public-source | ❌ cấm | ✅ đúng nguồn user chỉ định |
| sherlock/maigret/holehe/theHarvester/whois/dnsrecon | ❌ cấm | ✅ scope hẹp user duyệt |
| Reverse-geo online | ❌ cấm (dùng offline) | ✅ nguồn user chỉ định |
| Pentestcode/sqlmap lên scope | ❌ cấm | ❌ chỉ manual user |
| Brute force / wordlist / fuzz | ❌ cấm (bất biến) | ❌ cấm (bất biến) |
| ≥2 fact độc lập mới kết luận | ✅ | ✅ |
| Thiếu fact | BLOCKER | BLOCKER |

---

## 9. CHỐNG PHÁT HIỆN — KIẾN TRÚC VÔ HÌNH (như BotQuangAnh)

**Nguyên lý**: bot quang anh không thể bị phát hiện là AI agent vì MCP chạy
local — server CTF chỉ thấy HTTP từ IP/máy user. Bot dưa chuột giữ nguyên mô hình:

```
Server CTF thấy:  request HTTP bình thường từ máy user (như người thật)
Server CTF KHÔNG thấy: MCP · tunnel · client AI · skill · log local
```

**3 rào chắn cứng:**

| # | Rào chắn | Nội dung |
|---|---|---|
| 1 | Local-only bridge | MCP trên máy user; không thành phần nào trên hạ tầng CTF; IP máy user (không VPS/datacenter) |
| 2 | Zero AI fingerprint | Không UA opencode/ChatGPT/Claude ra wire; không gọi API LLM từ host lúc thi; không telemetry |
| 3 | Human-in-the-loop | Người duyệt bước lớn; người submit flag; bot chỉ chuẩn bị kết quả |

**OPSEC 8 luật cứng**: (1) local-first, tối thiểu request · (2) human
submission gate · (3) jitter 0.8–3s, tuần tự, không retry mù · (4) cấm tool
tự động lên scope, UA browser user · (5) zero outbound khi thi · (6) không
để dấu vết trên server (không upload thừa, không tạo account) · (7) log sạch,
tự dọn file tạm sau solve · (8) không DoS/crash instance; lỡ crash → BLOCKER.

---

## 10. CROSS-PLATFORM (Linux mọi arch + Windows)

**Chiến lược**: lõi Python thuần (mọi nền tảng) + Platform Adapter phân tầng:

```
python-portable  →  native PATH  →  package-mgr (apt/dnf/pacman/apk/zypper/
brew/winget/choco/scoop)  →  WSL2 (Windows)  →  container (arch hiếm)
```

| Tool | Linux x86_64 | ARM aarch64 | Alpine musl | Windows native | Windows WSL2 |
|---|---|---|---|---|---|
| exiftool (perl) | ✅ | ✅ | ✅ | ⚠️ Perl riêng | ✅ |
| exiv2 | ✅ | ✅ build | ⚠️ | ✅ | ✅ |
| ffmpeg/ffprobe | ✅ | ✅ | ✅ | ✅ | ✅ |
| tshark/tcpdump | ✅ | ✅ | ⚠️ build | ✅ | ✅ |
| binwalk/vol/Geo Engine (python) | ✅ | ✅ | ✅ | ✅ | ✅ |
| foremost/steghide (C) | ✅ | ⚠️ build | ⚠️ | ❌ | ✅ |
| sleuthkit | ✅ | ✅ build | ⚠️ | ✅ | ✅ |
| yara/tesseract | ✅ | ✅ build | ⚠️ | ✅ | ✅ |

Windows thêm: executor cmd/powershell-aware, path adapter (C:\ UNC
case-insensitive), `win_probe` (hives/$MFT/prefetch/LNK parser thuần python —
chạy được cả trên Linux khi phân tích offline).

---

## 11. DANH SÁCH TOOL MCP ĐẦY ĐỦ

**Core (kế thừa, 12):** health · capabilities · fs_list · fs_read · fs_write ·
fs_replace · fs_append · fs_mkdir · fs_search · cmd_check · cmd_run · knowledge

**Investigation (mới, 10):**

| Tool | Chức năng |
|---|---|
| `geo_extract` | ảnh/video → GPS thô, chéo exiftool+exiv2 |
| `coord_convert` | DMS/decimal/UTM/MGRS ↔ nhau, datum transform |
| `geo_calc` | distance/bearing/uncertainty (geodesic) |
| `geo_reverse` | offline landmark match |
| `geo_verify` | cross-check ≥2 fact, confidence score |
| `timezone_at` | lat/lon → timezone (offline) |
| `media_probe` | ảnh/audio/video: metadata + stream + frame |
| `pcap_probe` | flow + geo hints + carving |
| `disk_probe` | fls/fsstat + carve |
| `mem_probe` | vol3 profile + scan |
| `stego_probe` | LSB/audio/carrier detect |
| `ocr_probe` | tesseract + QR/barcode → tọa độ |
| `win_probe` | hives/$MFT/prefetch/LNK (thuần python) |

---

## 12. LỘ TRÌNH (M1–M6)

| Phase | Nội dung | Verify |
|---|---|---|
| **M1 Nền tảng** | Fork `app/` từ BotQuangAnh, đổi prefix `duachuot_*`, auth+tunnel | `duachuot health`, `config validate` |
| **M2 Geo Engine** | 5 module `app/geo/` + tests round-trip (DMS↔decimal↔UTM, datum) | `pytest tests/geo/` + 1 ảnh GPS thật |
| **M3 Tool Matrix** | TOOL_CATALOG +30 tool, cài geographiclib/piexif/zxing-cpp/tesseract, Platform Adapter | `duachuot knowledge tools --query geo --versions` |
| **M4 Skills** | 4 skill mới + playbook + routing từ solve-challenge | chạy triage → đúng skill |
| **M5 OPSEC + 2 chế độ** | OPSEC gate, `OSINT_MODE`, policy 2 chế độ, win_probe | test case ảnh GPS + username + domain |
| **M6 Dogfood** | 2 bài forensics + 2 bài OSINT mẫu, ghi solve_log + writeup | 4/4 có confidence score |

---

## 13. DEFINITION OF DONE

1. MCP server kết nối được từ ChatGPT/opencode (auth bắt buộc, tunnel operator-only).
2. Geo Engine pass round-trip byte-for-byte (decimal↔DMS↔UTM, datum transform).
3. Platform Adapter chạy trên Linux x86_64 + aarch64 + Windows (native/WSL2).
4. Resource Registry sinh RESOURCE_MAP.json từ kho ctf-tools; thiếu → BLOCKER.
5. OPSEC gate hoạt động: dry_run trước mỗi request, zero telemetry, human submit.
6. 4 skill mới load trong opencode, routing đúng từ solve-challenge.
7. Dogfood 4/4 bài có writeup + confidence score.
8. Tài liệu: README, SECURITY (policy 2 chế độ), PLAYBOOK ×3.

---

## 14. RỦI RO & GIẢM THIỂU

| Rủi ro | Giảm thiểu |
|---|---|
| Reverse-geo online cấm khi live | dataset offline landmarks + tz |
| Datum cũ làm lệch tọa độ 100–500m | ghi datum gốc, ghi chú độ lệch khi transform |
| EXIF bị strip / tọa độ trong carrier | pipeline chéo: exiftool+exiv2+stego+OCR barcode |
| Tool thiếu trên nền tảng lạ | Platform Adapter fallback python/WSL2/container |
| IP datacenter lộ (VPS) | chạy trên máy user; cấm VPS khi thi |
| Rate limit gateway LLM | model free riêng / chạy local |
| Pattern archive rỗng | lấp dần sau mỗi event qua pattern-record-proposal |

---

## 15. TÍNH NĂNG ĐỀ XUẤT

**P0 — bắt buộc (trong M1–M5):**
Platform Adapter · OPSEC gate (dry_run + jitter + zero-telemetry) ·
Resource Registry · executor shell-aware (bash/zsh/cmd/powershell).

**P1 — thêm sau M5:**
- `geo_verify` 3 nguồn (EXIF + hướng + landmark offline + timezone)
- OCR pipeline (tesseract + zxing-cpp QR chứa tọa độ)
- `win_probe` parser thuần python
- Cross-tool report gộp (exiftool+exiv2+ffprobe+ocr+stego cho 1 file)
- `duachuot plan` — sinh kế hoạch điều tra trước khi làm
- Confidence score chuẩn hoá 0–1 kèm lý do
- Challenge instance guard (phát hiện URL đổi giữa các lần gọi)
- Auto-cleanup hook sau solve

**Loại bỏ chủ động:** tự submit flag · pentestcode/sqlmap tự động lên scope ·
reverse-geo online khi ctf-live · telemetry/analytics trong bot.