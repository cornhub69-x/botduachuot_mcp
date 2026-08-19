# OSINT Playbook — BotDuaChuot

Chuẩn cho bài **OSINT**. Lưu ý cực kỳ quan trọng: **chế độ mặc định là `ctf-live`** — mọi công cụ tìm kiếm công khai (sherlock, maigret, whois, dnsrecon, search engine) **bị OPSEC gate chặn**. Chỉ bật `investigation` (`OSINT_MODE=true`) khi operator xác nhận challenge cho phép truy vấn bên ngoài.

## Pipeline

1. **Triage nguồn** — xác định dạng evidence: ảnh, text, username, domain, ảnh chụp màn hình, bài đăng.
2. **Local evidence trước** — mọi thứ có thể extract offline:
   - Ảnh: `duachuot_media_probe` + `duachuot_geo_extract` (GPS có thể là đáp án luôn).
   - `duachuot_ocr_probe` — văn bản/QR trong ảnh.
   - `duachuot_win_probe` / disk probe cho artifact.
3. **Kết nối fact** — liệt kê mọi chuỗi: username ↔ platform, domain ↔ cert, coords ↔ landmark (offline dataset), timestamp ↔ timezone.
4. **Chỉ khi investigation mode**: sherlock/maigret cho username, whois/dnsrecon cho domain, tìm theo cấu trúc câu hỏi.
5. **Verify** — mỗi kết luận cần >= 2 fact độc lập (vd: ảnh đăng + coords EXIF + landmark khớp).

## Bẫy thường gặp

| Bẫy | Xử lý |
|---|---|
| Coords trong EXIF nhưng là local time | so GPSDateTime vs timezone offline |
| Username trùng người khác | đối chiếu avatar/ngày đăng/timezone |
| Ảnh chụp màn hình map | OCR + nhận diện landmark/đường phố |
| Domain hints qua cert | openssl s_client -showcerts (không brute) |
| Metadata đã bị strip | kiểm tra thumbnail, comment, filename, tạo thời |

## OPSEC (nhắc lại)

- Không chạy web search khi live.
- Không chạy tool enumeration vào bất kỳ infra nào thuộc scope của challenge.
- Trước mỗi truy vấn mạng: `duachuot_ops_check(kind='remote')`; giữa các truy vấn: `duachuot_ops_jitter`.
- Không bao giờ submit flag tự động — luôn qua người dùng.
- Mọi log phải qua `duachuot_ops_redact` trước khi lưu.

## Fact ghi nhận

- FACT: chuỗi trích xuất + nguồn chính xác (file, offset, tool).
- INFERENCE: suy luận có dẫn chứng (vd: timezone + timestamp → múi giờ local).
- HYPOTHESIS: giả thuyết chưa đủ fact.
- BLOCKER: thiếu quyền truy cập / bị chặn bởi mode → báo rõ.
