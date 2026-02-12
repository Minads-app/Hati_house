# Bamboo Resort - Hotel Management System

Hệ thống quản lý khách sạn với tính năng đặt phòng online cho The Bamboo Resort.

## 🌟 Tính năng

- ✅ Quản lý phòng và loại phòng
- ✅ Đặt phòng tại quầy (Counter Booking)
- ✅ Đặt phòng online cho khách hàng
- ✅ Quản lý dịch vụ phòng & F&B
- ✅ Báo cáo tài chính
- ✅ Hệ thống thanh toán VietQR
- ✅ Quản lý giá theo ngày thường/cuối tuần/lễ tết

## 🚀 Deploy lên Streamlit Cloud

Xem hướng dẫn chi tiết trong file `DEPLOYMENT.md` hoặc tại [đây](./DEPLOYMENT.md)

### Quick Start

1. **Tạo secrets cho Streamlit Cloud**:
   ```bash
   python generate_secrets.py
   ```
   Copy output và paste vào Streamlit Cloud > Advanced Settings > Secrets

2. **Push code lên GitHub**:
   ```bash
   git add .
   git commit -m "Deploy to Streamlit Cloud"
   git push origin main
   ```

3. **Deploy**: Truy cập https://share.streamlit.io và tạo app mới

## 📦 Cài đặt Local

```bash
# Clone repository
git clone https://github.com/[your-username]/bamboo-resort.git
cd bamboo-resort

# Tạo virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Cài đặt dependencies
pip install -r requirements.txt

# Chạy ứng dụng
streamlit run main.py
```

## 🔑 Cấu hình Firebase

1. Tạo project trên Firebase Console
2. Tải file `firebase_key.json` về
3. Đặt file vào thư mục gốc của project
4. File này đã được ignore trong `.gitignore` để bảo mật

## 📱 Link Booking Online

Sau khi deploy, link đặt phòng online sẽ là:
```
https://[your-app-name].streamlit.app/OnlineBooking
```

## 🛠️ Tech Stack

- **Frontend**: Streamlit
- **Database**: Firebase Firestore
- **Authentication**: Custom session-based auth
- **Payment**: VietQR integration
- **Charts**: Plotly

## 📞 Hỗ trợ

Nếu gặp vấn đề khi deploy, xem file `DEPLOYMENT.md` hoặc liên hệ support.
