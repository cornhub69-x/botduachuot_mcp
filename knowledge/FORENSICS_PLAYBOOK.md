# Forensics Playbook — BotDuaChuot

Chuẩn cho bài **forensics** (media, pcap, disk, memory, stego, windows artifacts). Evidence-first: chỉ kết luận khi có >= 2 fact độc lập hoặc 1 fact + chuỗi suy luận rõ.

## Pipeline theo loại artifact

### Media (ảnh/video)
1. `duachuot_media_probe` — file + exiftool JSON + ffprobe streams.
2. `duachuot_geo_extract` nếu có GPS; else kiểm tra: thumbnail, comment, XPComment, Creator, Software, timestamps (GPSDateTime/ModifyDate khác nhau → travel hint).
3. `duachuot_stego_probe` — binwalk + steghide info (payload có thể chứa tọa độ/flag).
4. `duachuot_ocr_probe` — tesseract text + QR (zxing-cpp) — QR thường chứa coord.
5. Nghi ngờ LSB: zsteg, thử các plane (stegsolve).

### PCAP
1. `duachuot_pcap_probe` — conversations, endpoints, DNS queries.
2. Geo hints: Wi-Fi probe requests (SSID/AP MAC → landmark), GPS NMEA (`$GPRMC`/`$GPGGA` trong data), cellular/Bluetooth.
3. Lọc flag: `tshark -Y` + strings; tải file theo dòng (HTTP) để inspect.
4. Nếu flow SSH/TLS với cert: extract cert (CN/SAN có thể là domain hint).

### Disk image
1. `duachuot_disk_probe` — file → fsstat (type/version) → fls -r (cây file, deleted files có `*`).
2. Quan sát: user profile, desktop, documents, bash history, browser history, recent files.
3. Carve: binwalk / foremost vào scratch dir (không bao giờ ghi lên bản gốc).
4. Passwords/hint: strings trên các file nghi vấn.

### Memory
1. `duachuot_mem_probe` — info (profile) → pslist → filescan theo evidence.
2. Tìm: clipboard, network connections (netstat), dumps văn bản, process với tên lạ, env/command line.
3. Cảnh báo: không nhảy tới plugin mà profile chưa chứng minh.

### Stego
1. Signature scan (binwalk), steghide info, zsteg cho LSB.
2. Nếu cần passphrase: chú ý hint trong tên file, metadata, nội dung bài.
3. **Không brute-force trên scope** (OPSEC rule 4).

### Windows artifacts (khi không có Windows host)
1. `duachuot_win_probe` — SAM/SYSTEM hive strings, LNK target strings, prefetch.
2. Kiểm tra RecentDocs, user.config, bộ office recent.

## Nguyên tắc

- **Preserve original**: mọi phân tích/output vào `/tmp` hoặc derived dir; đọc gốc read-only.
- **Carve vào scratch**: foremost/binwalk output ở thư mục riêng.
- **Tool thiếu ≠ suy luận**: nếu `tshark`/`vol` thiếu → trả về BLOCKER rõ, không đoán kết quả.
- **Version thật trên wire**: nếu challenge hỏi version tool, chạy version_args thật, không tự khai.
- **Evidence chain**: ghi file nguồn + command + output excerpt cho mọi fact.

## Fact ghi nhận

- FACT: giá trị + nguồn (tool, offset, file).
- INFERENCE: suy luận có dẫn chứng.
- HYPOTHESIS: chưa đủ fact → chờ bước tiếp theo.
- BLOCKER: thiếu công cụ/dữ liệu không thể tiếp tục → báo cụ thể thiếu gì.
