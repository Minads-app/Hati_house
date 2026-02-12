# 🚀 Hướng dẫn Deploy HATI House lên Streamlit Cloud

## Tổng quan

```mermaid
graph LR
    A["Code trên máy"] -->|git push| B["GitHub Repository"]
    B -->|kết nối| C["Streamlit Cloud"]
    C -->|deploy| D["App Online 🌐"]
```

> [!IMPORTANT]
> Code phải được đẩy lên **GitHub** (miễn phí). Streamlit Cloud sẽ đọc code từ GitHub để chạy app.

---

## Bước 1: Tạo GitHub Repository

1. Vào [github.com](https://github.com) → Đăng ký/Đăng nhập
2. Click **"New repository"** (dấu `+` góc phải)
3. Đặt tên: `hati-house` (hoặc tên bạn muốn)
4. Chọn **Private** (để code không công khai)
5. **KHÔNG** tick "Add README" (vì đã có sẵn)
6. Click **"Create repository"**

---

## Bước 2: Push code lên GitHub

Mở **Terminal/PowerShell** tại thư mục dự án `Hati_House`, chạy lần lượt:

```bash
# 1. Khởi tạo git
git init

# 2. Thêm tất cả file (trừ những file trong .gitignore)
git add .

# 3. Tạo commit đầu tiên
git commit -m "Initial commit - HATI House"

# 4. Kết nối với GitHub repo (thay YOUR_USERNAME bằng tên GitHub của bạn)
git remote add origin https://github.com/YOUR_USERNAME/hati-house.git

# 5. Push code lên
git branch -M main
git push -u origin main
```

> [!CAUTION]
> Kiểm tra trước khi push: chạy `git status` để đảm bảo **KHÔNG** có `firebase_key.json` hay `secrets.toml` trong danh sách file. File `.gitignore` đã tự động ẩn chúng.

---

## Bước 3: Tạo Firebase Secrets (TOML format)

Trên máy local, chạy:

```bash
python generate_secrets.py
```

Script sẽ in ra nội dung TOML, ví dụ:

```toml
[firebase]
type = "service_account"
project_id = "your-project-id"
private_key_id = "abc123..."
private_key = "-----BEGIN PRIVATE KEY-----\\nMIIE...\\n-----END PRIVATE KEY-----\\n"
client_email = "firebase-adminsdk-xxx@your-project.iam.gserviceaccount.com"
...
```

**📋 Copy toàn bộ nội dung này** (bao gồm dòng `[firebase]`).

---

## Bước 4: Deploy trên Streamlit Cloud

1. Vào [share.streamlit.io](https://share.streamlit.io) → Đăng nhập bằng GitHub
2. Click **"New app"**
3. Chọn:
   - **Repository**: `YOUR_USERNAME/hati-house`
   - **Branch**: `main`
   - **Main file path**: `main.py`
4. Mở **"Advanced settings"** → **Secrets**:
   - **Paste** nội dung TOML từ Bước 3 vào đây
5. Click **"Deploy!"**

> [!TIP]
> App sẽ mất 2-3 phút để build lần đầu. Sau đó, mỗi lần `git push` code mới lên GitHub → Streamlit Cloud sẽ tự động re-deploy.

---

## Bước 5: Kiểm tra

Sau khi deploy thành công, bạn sẽ nhận được URL dạng:

```
https://YOUR_USERNAME-hati-house-main-xxxxx.streamlit.app
```

Kiểm tra:
- [ ] Đăng nhập được
- [ ] Sơ đồ phòng hiển thị đúng
- [ ] Tạo booking thành công
- [ ] Trang Online Booking hoạt động

---

## Cập nhật code sau này

Mỗi lần sửa code trên máy, chỉ cần:

```bash
git add .
git commit -m "Mô tả thay đổi"
git push
```

Streamlit Cloud sẽ tự **re-deploy** trong vòng 1-2 phút.

---

## Khắc phục sự cố thường gặp

| Lỗi | Nguyên nhân | Cách sửa |
|-----|-------------|----------|
| `ModuleNotFoundError` | Thiếu thư viện | Kiểm tra `requirements.txt` |
| `Firebase credentials not found` | Chưa paste Secrets | Vào App Settings > Secrets |
| `private_key error` | Sai format newline | Dùng `\\n` (2 ký tự) thay vì xuống dòng thật |
| App crash loop | Lỗi code | Xem log tại Streamlit Cloud dashboard |
