# Hướng dẫn máy xưởng — QR Live Scanner 1.0.0

1. Tải `QRLiveScanner-Setup.exe` từ Releases của repo `huybitvvt/qr-live-scanner`.
   Nếu cần đối chiếu file, dùng SHA-256 trong `SHA256SUMS.txt` cùng bản phát hành.
2. Chạy bộ cài. Không cần Python, Internet hoặc key để quét. Bộ cài chưa ký
   Authenticode; Windows có thể hiện SmartScreen. Chỉ chạy file từ đúng repo.
3. Mở **QR Live Scanner** trên Desktop. Camera mở và quét tự động.
4. Không thấy hình: chọn Camera 1, 2… rồi **Mở camera**. Thử driver
   **Media Foundation** nếu DirectShow không mở được. Đóng ứng dụng khác đang
   chiếm cùng camera; kiểm tra quyền Camera trong Windows Settings.
5. Đưa tem vào hình; giữ đủ rõ để ứng dụng xác nhận hai frame. Không bấm chụp.
   Mã vừa đọc hiện dưới camera và ghi vào lịch sử. Giữ tem trước camera không
   làm lịch sử tăng liên tục. Đưa ra trên 1,5 giây rồi đưa lại để quét lượt mới.
6. **Chọn vùng QR** rồi kéo chuột khoanh toàn bộ tem và viền trắng. **Toàn khung**
   để bỏ vùng chọn. Không chọn vùng quá sát làm cắt góc QR.
7. **Sao chép** lấy mã gần nhất. Nhấp đúp dòng lịch sử lấy mã của dòng đó.
   **Xuất CSV** lưu toàn bộ lịch sử hiện có để mở bằng Excel.
8. **Dừng** giải phóng camera. **Mở camera** hoặc F5 mở lại. Đóng cửa sổ để thoát.

Mã vùng quét được nhớ theo lựa chọn camera/driver. Lịch sử, cấu hình và log ở
`%LOCALAPPDATA%\QRLiveScanner`; không nằm trong thư mục cài đặt trạm cân.
Gỡ/cài lại không xóa lịch sử. Không có ảnh camera được gửi Internet hoặc lưu nền.

Để chạy liên tục: giữ máy cắm điện, tắt Sleep theo chính sách của xưởng, kiểm tra
lấy nét/ánh sáng và tránh ứng dụng khác chiếm camera. Có thể chọn **Start scanner
when signing in to Windows** khi cài đặt nếu muốn tự mở khi đăng nhập.

Thanh cuối hiện CPU tổng của ứng dụng/các worker, RAM, thời gian xử lý lượt
gần nhất, số lần dùng WeChat và thời gian mở ứng dụng. Đây là số đo tại máy,
không phải cam kết FPS hay tỷ lệ đọc đúng.

Khi báo lỗi, gửi phiên bản, ảnh chụp màn hình và `app.log`/`health.json` trong
thư mục dữ liệu. Không cần gửi `history.db` vì có thể chứa mã sản phẩm của xưởng.
