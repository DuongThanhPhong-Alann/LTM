# ⚡ QUICK START - TÍNH NĂNG QUÊN MẬT KHẨU

## 🎯 Triển Khai Nhanh Trong 5 Phút

### Bước 1: Cập Nhật Database (1 phút)
```
1. Vào Supabase Dashboard → SQL Editor
2. Mở file: database/forgot_password_schema.sql
3. Copy toàn bộ → Paste → Run
4. Kiểm tra: SELECT * FROM users LIMIT 1; (phải thấy cột temp_password)
```

### Bước 2: Setup n8n (2 phút)
```
1. Mở n8n: http://localhost:5678
2. Import from File → Chọn: n8n/forgot_password_email_workflow.json
3. Click node "Send Forgot Password Email" → Cấu hình Gmail
4. Click "Active" để kích hoạt workflow
5. Copy webhook URL (ví dụ: http://localhost:5678/webhook/forgot-password)
```

### Bước 3: Cấu Hình Flask (1 phút)
```python
# Mở web/app.py, tìm dòng 238:
n8n_webhook_url = "http://localhost:5678/webhook/forgot-password"
# Thay bằng URL từ bước 2 (nếu khác)
```

### Bước 4: Cài Dependencies (30 giây)
```bash
cd web
pip install requests bcrypt supabase
```

### Bước 5: Khởi Động (30 giây)
```bash
# Terminal 1: n8n
n8n start

# Terminal 2: Flask
cd web
python app.py
```

---

## ✅ Kiểm Tra Hoạt Động

1. Truy cập: `http://127.0.0.1:5000/login`
2. Nhấn **"Quên mật khẩu?"**
3. Nhập email đã đăng ký → Gửi
4. Kiểm tra email → Copy mật khẩu tạm (8 ký tự)
5. Đăng nhập bằng mật khẩu tạm
6. Đổi mật khẩu mới
7. ✅ Hoàn tất!

---

## 📋 Các File Đã Tạo/Sửa

**Files MỚI:**
- `database/forgot_password_schema.sql` - SQL schema
- `n8n/forgot_password_email_workflow.json` - n8n workflow
- `web/templates/force_change_password.html` - Trang đổi mật khẩu
- `HUONG_DAN_QUEN_MAT_KHAU.md` - Tài liệu chi tiết
- `QUICK_START_FORGOT_PASSWORD.md` - File này

**Files ĐÃ CẬP NHẬT:**
- `web/services/user_service.py` - Thêm 5 methods mới
- `web/app.py` - Thêm 2 routes mới
- `web/templates/login.html` - Thêm nút "Quên mật khẩu?" + modal

---

## 🔧 Cấu Hình Quan Trọng

### Webhook URL
```python
# web/app.py (line 238)
n8n_webhook_url = "http://localhost:5678/webhook/forgot-password"
```
⚠️ **Phải khớp với URL trong n8n workflow!**

### Thời Gian Hết Hạn
```python
# web/services/user_service.py (line 464)
expires_at = (datetime.now() + timedelta(minutes=2)).isoformat()
```
⏱️ **Mặc định: 2 phút**

### Gmail Credentials
```
n8n → Node "Send Forgot Password Email" → Credentials
→ Add New → Gmail OAuth2 → Authorize
```
📧 **Phải authorize Gmail account**

---

## 🐛 Troubleshooting

| Lỗi | Giải pháp |
|-----|-----------|
| "Không thể kết nối đến dịch vụ email" | Kiểm tra n8n đã chạy, workflow đã active |
| "Email không tồn tại trong hệ thống" | Email chưa đăng ký hoặc chưa verify |
| Email không gửi được | Re-authorize Gmail trong n8n |
| Database error | Chạy lại SQL script trong Supabase |

---

## 📞 Cần Giúp Đỡ?

Đọc tài liệu chi tiết: `HUONG_DAN_QUEN_MAT_KHAU.md`

Kiểm tra logs:
```bash
# Flask logs
python app.py  # xem terminal output

# n8n logs
n8n start  # xem terminal output

# Supabase logs
Dashboard → Logs
```

---

## 🎉 Done!

Giờ người dùng có thể:
- ✅ Quên mật khẩu → Nhận email mật khẩu tạm
- ✅ Đăng nhập bằng temp password (2 phút)
- ✅ Bắt buộc đổi mật khẩu mới
- ✅ Hoặc vẫn đăng nhập bằng mật khẩu chính

**Thời gian triển khai:** ~5 phút
**Bảo mật:** ✅ Hash, Expire, Force Change
**UI/UX:** ✅ Đẹp, Responsive, Dễ dùng
