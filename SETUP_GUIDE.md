# HƯỚNG DẪN CÀI ĐẶT CHO RESORT MỚI (SETUP GUIDE)

Tài liệu này hướng dẫn cách đóng gói và triển khai ứng dụng quản lý khách sạn cho một khách hàng mới (ví dụ: Mui Nai Resort).

## 1. Chuẩn bị
Trước khi bắt đầu, bạn cần có:
1.  **Source Code**: Copy toàn bộ thư mục dự án hiện tại sang thư mục mới cho khách hàng.
2.  **Firebase Key**: File credential `.json` từ Firebase Console của dự án mới.
    *   Đặt file này vào thư mục `config/` (ví dụ: `config/mui_nai_key.json`).

## 2. Cấu hình tự động
Chúng tôi đã chuẩn bị sẵn một script để tự động hóa việc cấu hình.

1.  Mở Terminal tại thư mục dự án.
2.  Chạy lệnh sau:
    ```bash
    python create_resort.py
    ```
3.  Nhập các thông tin được yêu cầu:
    *   **Resort Name**: Tên hiển thị (VD: Mui Nai Resort)
    *   **Page Title**: Tiêu đề trang web
    *   **Page Icon**: Icon hiển thị trên tab trình duyệt (VD: 🌊)
    *   **Firebase Filename**: Tên file key bạn đã để trong thư mục config (VD: `mui_nai_key.json`)

Script sẽ tự động tạo ra:
*   File `.env`: Cấu hình môi trường.
*   File `run_resort.bat`: Script khởi động nhanh dành cho khách hàng.

## 3. Chạy ứng dụng
Sau khi cấu hình xong, bạn có thể chạy ứng dụng bằng cách:

*   **Cách 1 (Dễ nhất)**: Double-click vào file `run_resort.bat` vừa được tạo.
*   **Cách 2 (Thủ công)**: Chạy lệnh `streamlit run main.py`.

## 4. Kiểm tra
*   Mở trình duyệt.
*   Kiểm tra Tiêu đề tab và Header sidebar xem đã đúng tên Resort mới chưa.
*   Thử đăng nhập và kiểm tra dữ liệu (đảm bảo nó kết nối tới Firebase mới chứ không phải cái cũ).

---
**Lưu ý:**
*   Nếu muốn thay đổi logo, hãy thay thế file `config/logo.png`.
*   Để reset cấu hình, chỉ cần chạy lại `python create_resort.py`.
