# Kiểm chứng QR Live Scanner 1.0.0 — 04/11/2026

## Môi trường

- Windows 11 x64; Intel Core i3-1215U, 8 logical CPUs, khoảng 8 GB RAM.
- Python 3.14.3, OpenCV contrib headless 4.13.0.92, ZXing-C++ 3.1.1.
- Bộ cài PyInstaller 6.22.3 + Inno Setup 6; có Python runtime, DLL và model.
- Không dùng camera/ảnh/DB/config vận hành của ứng dụng trạm cân.

## Đã kiểm chứng

- **14 test Python đạt**: ZXing và WeChat chạy model thật, fallback WeChat
  xác nhận hai frame, giới hạn gọi khi nền trống, chống lặp và quét lại khi
  tem rời camera, giới hạn bộ nhớ xác nhận, kiểm tra vùng quét/checksum model,
  latest-frame IPC, tiến trình spawn, phục hồi decoder bị terminate, lịch sử
  SQLite và CSV có bảo vệ công thức bảng tính.
- `pip check` đạt.
- Giao diện native chạy thật: đọc mã, sao chép clipboard, xuất CSV, kéo chọn
  vùng, nạp lại worker, đọc QR sau đổi vùng, Dừng và Toàn khung đều đạt.
- Source phát video tổng hợp theo thời gian thực: đọc đúng **8/8 mã theo thứ tự**,
  mỗi mã giữ nhiều frame nhưng chỉ ghi một lượt. Video có các đoạn nền trống.
- EXE cuối chạy **90 giây** với nguồn ảnh tổng hợp 1280×720 lặp 30 FPS:
  chỉ ghi một dòng QR; không restart camera/decoder; CPU trung bình **4,14%**
  của toàn bộ 8 logical CPUs, RAM các tiến trình cộng lại **171,9–175,9 MB**.
  Có khoảng 883 lượt quét trong 90 giây. Đây không phải đo tốc độ bắt mã từ
  camera vật lý; không suy ra khả năng chạy 24 giờ từ bài kiểm tra này.
- Bộ cài được cài silent vào thư mục kiểm chứng riêng, exit code **0**;
  SHA-256 EXE đã cài khớp EXE đã build. Không tạo shortcut khởi động Windows
  hoặc cài đè ứng dụng đang vận hành trong bài kiểm tra.
- **Bản EXE sau cài** phát video tổng hợp 50 giây: đọc đúng **8/8 mã theo thứ tự**,
  không ghi lặp, 402 lượt quét và 17 lần fallback WeChat, exit code **0**.
- Ảnh giao diện và dữ liệu đo: [ảnh](docs/screenshot.png),
  [EXE 90 giây](docs/evidence-frozen.json), [bản đã cài](docs/evidence-installed.json).

## Chưa nghiệm thu

- Camera USB, driver, quyền camera và ánh sáng thực tế của máy xưởng.
- Tỷ lệ đọc đúng trên tem thật, đặc biệt tem nhỏ, cong, lóa và nhòe.
- Chạy liên tục 24/72 giờ, mất điện, rút/cắm camera thật, nhiệt độ CPU.
- Windows 10 trên máy sạch; bản build được chạy trên Windows 11 có Python
  cài ở máy phát triển, nhưng EXE tự mang runtime và không gọi Python ngoài.
- Chứng thư Authenticode: bộ cài **chưa ký**.

Không công bố FPS hay tỷ lệ đọc đúng cho mọi camera. Giới hạn nhịp quét là
chính sách điều phối, không phải cam kết hiệu năng phần cứng.

## Tái lập

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe tools\make_fixture.py
$env:PYTHONPATH = (Get-Location).Path
.venv\Scripts\python.exe tools\smoke_controls.py
.venv\Scripts\python.exe tools\smoke_app.py --exe dist\QRLiveScanner\QRLiveScanner.exe --name frozen-release --seconds 90
```

Các thư mục smoke phải chưa tồn tại. Không xóa dữ liệu của lần kiểm chứng cũ
để dùng lại tên; chọn tên khác cho mỗi lần chạy.
