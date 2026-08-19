# Geo Playbook — BotDuaChuot

Chuẩn cho mọi bài toán **tọa độ / vị trí** trong CTF. Mục tiêu: tìm tọa độ chính xác, chứng minh bằng >= 2 fact độc lập, offline và deterministic.

## Pipeline (8 bước chuẩn)

1. **Triage artifact** — `duachuot_media_probe` (hoặc `file` + `exiftool -json -n`). Xác định loại file, nguồn metadata.
2. **Trích xuất GPS** — `duachuot_geo_extract(path, cross_check=True)`. exiftool là primary, exiv2 là cross-check. **Nếu 2 nguồn bất đồng → trả về None + cảnh báo; không bao giờ merge yên lặng.**
3. **Convert** — `duachuot_coord_convert` với mọi dạng tọa độ gặp trong challenge:
   - DMS: `21°01'44.6"N 105°51'13.2"E` (chú ý N/S/E/W)
   - Decimal: `21.02906, 105.85367`
   - UTM: zone + hemisphere + easting/northing (ED50/NAD27/WGS84 khác nhau tới 100-500 m!)
   - MGRS: `48Q UJ 12345 67890` (chuẩn NGA: zone lẻ dùng set cột 8 ký tự, zone chẵn dùng set hàng 20 ký tự)
4. **Reverse offline** — `duachuot_geo_reverse` với dataset landmarks.json. Luôn note đây là offline estimate, không phải GPS thật.
5. **Verify** — `duachuot_geo_verify`: cần >= 2 fact độc lập (landmark gần, timezone khớp, heading khớp, EXIF). < 2 → **BLOCKER**, không được kết luận.
6. **Cross-check time** — `duachuot_timezone_at` so với GPSDateTime trong EXIF (UTC → local).
7. **Cross-check heading** — bearing từ điểm chụp tới landmark vs GPSImgDirection.
8. **Báo cáo** — ghi fact/inference rõ ràng, kèm accuracy (HPE/DOP), dẫn nguồn từng value.

## Nguyên tắc

- **Offline tuyệt đối**: không dùng reverse-geocoding online (Google/OSM API) khi đang live. Nếu dataset thiếu landmark, ghi BLOCKER.
- **Round-trip byte-for-byte**: mọi convert phải qua lại đúng; test round-trip là bắt buộc trước khi tin một kết quả.
- **Datum là bẫy kinh điển**: bài hay cho UTM/ED50 hoặc "Lat: 21 01 44.6 N". Luôn thử cả 3 datum khi kết quả không khớp landmark.
- **Accuracy đi kèm mọi kết luận**: luôn output bán kính sai số (DOP*HPE hoặc ước lượng).

## Bẫy thường gặp

| Bẫy | Dấu hiệu | Xử lý |
|---|---|---|
| Lat/Lon đảo | landmark cách xa | thử đảo trục |
| DMS thiếu dấu phút/giây | "21 01 44.6" | parse decimal thuần |
| MGRS zone chẵn/lẻ | square không hợp lệ | dùng bảng NGA đúng |
| Datum ED50/NAD27 | lệch 100-500 m đều | transform → WGS84 |
| GPSDateTime local vs UTC | timezone không khớp | thử offset 7/8 giờ |

## Fact ghi nhận

- FACT: giá trị trích xuất được + nguồn (exiftool/exiv2/nơi đọc).
- INFERENCE: suy luận có dẫn chứng (bearing + heading → hướng chụp).
- HYPOTHESIS: giả thuyết chưa đủ fact (cần bước verify).
- BLOCKER: không đủ fact độc lập → không kết luận, báo thiếu gì.
