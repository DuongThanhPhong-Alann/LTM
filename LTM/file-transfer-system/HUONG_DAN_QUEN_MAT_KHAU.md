# 🔐 HƯỚNG DẪN TRIỂN KHAI TÍNH NĂNG QUÊN MẬT KHẨU

## 📋 Tổng Quan

Tính năng quên mật khẩu cho phép người dùng khôi phục tài khoản bằng cách nhận mật khẩu tạm qua email. Mật khẩu tạm có hiệu lực **2 phút** và người dùng sẽ được yêu cầu đổi mật khẩu mới sau khi đăng nhập.

### ✨ Tính Năng Chính

- ✅ Tạo mật khẩu tạm ngẫu nhiên 8 ký tự (3 chữ hoa + 3 chữ thường + 2 số)
- ✅ Gửi email thông báo mật khẩu tạm qua n8n
- ✅ Mật khẩu tạm tự động hết hạn sau 2 phút
- ✅ Hỗ trợ đăng nhập bằng cả mật khẩu chính và mật khẩu tạm
- ✅ Bắt buộc đổi mật khẩu mới sau khi đăng nhập bằng mật khẩu tạm
- ✅ Giao diện đẹp, responsive, trải nghiệm người dùng tốt

---

## 🚀 CÁC BƯỚC TRIỂN KHAI

### 1. Cập Nhật Database Schema (Supabase)

**File:** `database/forgot_password_schema.sql`

Truy cập Supabase Dashboard → SQL Editor → Paste và chạy toàn bộ nội dung file SQL này.

**Những gì được tạo:**
- Thêm 3 cột vào bảng `users`:
  - `temp_password` (VARCHAR): Lưu mật khẩu tạm đã hash
  - `temp_password_expires_at` (TIMESTAMP): Thời gian hết hạn
  - `require_password_change` (BOOLEAN): Flag yêu cầu đổi mật khẩu

- Tạo các stored functions:
  - `generate_temp_password()`: Tạo mật khẩu tạm ngẫu nhiên
  - `create_temp_password_for_user(email)`: Tạo mật khẩu tạm cho user
  - `cleanup_expired_temp_passwords()`: Xóa mật khẩu tạm hết hạn
  - `clear_temp_password(userid)`: Xóa temp password sau khi đổi mật khẩu

**Kiểm tra:**
```sql
-- Kiểm tra cột đã được thêm
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name IN ('temp_password', 'temp_password_expires_at', 'require_password_change');

-- Kiểm tra functions
SELECT routine_name
FROM information_schema.routines
WHERE routine_type = 'FUNCTION'
AND routine_name LIKE '%temp_password%';
```

---

### 2. Import Workflow N8N

**File:** `n8n/forgot_password_email_workflow.json`

**Bước thực hiện:**

1. Mở n8n Dashboard (thường là `http://localhost:5678`)

2. Nhấn **"Import from File"** → Chọn file `forgot_password_email_workflow.json`

3. **Cấu hình Gmail Node:**
   - Nhấn vào node "Send Forgot Password Email"
   - Chọn hoặc tạo mới **Gmail OAuth2 Credentials**
   - Authorize Gmail account (sử dụng Gmail của bạn)

4. **Lấy Webhook URL:**
   - Nhấn vào node "Webhook - Forgot Password"
   - Copy URL webhook (ví dụ: `http://localhost:5678/webhook/forgot-password`)
   - Lưu URL này để cấu hình trong Flask app

5. **Activate Workflow:**
   - Nhấn nút **"Active"** ở góc trên bên phải
   - Đảm bảo status chuyển sang màu xanh

6. **Test Workflow:**
   - Nhấn **"Execute Workflow"** với test data:
   ```json
   {
     "email": "test@example.com",
     "username": "testuser",
     "temp_password": "ABCabc12",
     "timestamp": "2025-01-15T10:30:00",
     "login_url": "http://127.0.0.1:5000/login",
     "expires_in_minutes": 2
   }
   ```
   - Kiểm tra email đã nhận được chưa

---

### 3. Cập Nhật Flask App

**File đã được cập nhật:**
- `web/services/user_service.py` - Thêm methods xử lý temp password
- `web/app.py` - Thêm routes cho forgot password
- `web/templates/login.html` - Thêm nút "Quên mật khẩu?" và modal
- `web/templates/force_change_password.html` - Trang đổi mật khẩu bắt buộc (MỚI)

**Cấu hình Webhook URL:**

Mở file `web/app.py`, tìm dòng:
```python
n8n_webhook_url = "http://localhost:5678/webhook/forgot-password"
```

Thay thế bằng URL webhook thực tế từ bước 2 (nếu khác).

**Lưu ý:** Nếu n8n chạy trên server khác hoặc domain khác, thay đổi URL tương ứng.

---

### 4. Cài Đặt Dependencies

Đảm bảo bạn đã cài đặt các thư viện Python cần thiết:

```bash
cd web
pip install requests bcrypt supabase
```

Các thư viện:
- `requests` - Gửi HTTP request đến n8n webhook
- `bcrypt` - Hash mật khẩu tạm
- `supabase` - Kết nối Supabase database

---

### 5. Khởi Động Hệ Thống

**Bước 1: Khởi động n8n**
```bash
# Nếu chưa cài n8n
npm install -g n8n

# Khởi động n8n
n8n start
```

**Bước 2: Khởi động Flask App**
```bash
cd web
python app.py
```

**Bước 3: Truy cập ứng dụng**
- Mở trình duyệt: `http://127.0.0.1:5000/login`

---

## 🎯 HƯỚNG DẪN SỬ DỤNG

### Cho Người Dùng

1. **Quên mật khẩu:**
   - Truy cập trang đăng nhập
   - Nhấn link **"Quên mật khẩu?"**
   - Nhập email đã đăng ký
   - Nhấn **"Gửi Mật Khẩu Tạm"**

2. **Nhận email:**
   - Kiểm tra hộp thư email
   - Mở email "🔐 [QUAN TRỌNG] Mật Khẩu Tạm Thời..."
   - Copy mật khẩu tạm (8 ký tự)

3. **Đăng nhập bằng mật khẩu tạm:**
   - Quay lại trang đăng nhập
   - Nhập username và mật khẩu tạm
   - Nhấn **"Đăng nhập"**

4. **Đổi mật khẩu mới:**
   - Hệ thống tự động chuyển đến trang đổi mật khẩu
   - Nhập mật khẩu mới (phải đáp ứng yêu cầu)
   - Nhập lại mật khẩu mới để xác nhận
   - Nhấn **"Xác Nhận Đổi Mật Khẩu"**

5. **Hoàn tất:**
   - Mật khẩu đã được cập nhật
   - Lần đăng nhập sau sử dụng mật khẩu mới

---

## 🔒 BẢO MẬT

### Cơ Chế Bảo Mật

1. **Mật khẩu tạm ngẫu nhiên:**
   - 8 ký tự random (3 uppercase + 3 lowercase + 2 digits)
   - Ví dụ: `ABCabc12`, `XYZxyz89`

2. **Hash mật khẩu:**
   - Mật khẩu tạm được hash bằng bcrypt trước khi lưu database
   - Không lưu plaintext

3. **Thời gian hết hạn:**
   - Mật khẩu tạm tự động hết hạn sau **2 phút**
   - Hệ thống tự động xóa mật khẩu tạm khi hết hạn

4. **Đa lớp xác thực:**
   - Email phải đã được verify
   - Chỉ gửi mật khẩu tạm cho email đã đăng ký

5. **Bắt buộc đổi mật khẩu:**
   - Sau khi đăng nhập bằng temp password, user **BẮT BUỘC** phải đổi mật khẩu mới
   - Không thể bypass trang đổi mật khẩu

---

## 🧪 KIỂM THỬ

### Test Case 1: Quên mật khẩu thành công

**Điều kiện:**
- User đã đăng ký và verify email
- Email tồn tại trong database

**Các bước:**
1. Nhấn "Quên mật khẩu?" trên trang login
2. Nhập email: `test@example.com`
3. Nhấn "Gửi Mật Khẩu Tạm"

**Kết quả mong đợi:**
- ✅ Hiển thị thông báo thành công
- ✅ Email được gửi đến hộp thư
- ✅ Email chứa mật khẩu tạm 8 ký tự
- ✅ Trong database, cột `temp_password` và `temp_password_expires_at` được cập nhật

### Test Case 2: Email không tồn tại

**Các bước:**
1. Nhấn "Quên mật khẩu?"
2. Nhập email: `notexist@example.com`
3. Nhấn "Gửi Mật Khẩu Tạm"

**Kết quả mong đợi:**
- ❌ Hiển thị lỗi: "Email không tồn tại trong hệ thống"

### Test Case 3: Đăng nhập bằng mật khẩu tạm

**Điều kiện:**
- Đã nhận được mật khẩu tạm qua email
- Chưa quá 2 phút kể từ khi nhận

**Các bước:**
1. Truy cập trang login
2. Nhập username: `testuser`
3. Nhập mật khẩu tạm: `ABCabc12`
4. Nhấn "Đăng nhập"

**Kết quả mong đợi:**
- ✅ Đăng nhập thành công
- ✅ Tự động redirect đến trang đổi mật khẩu
- ✅ Hiển thị warning: "Vui lòng đổi mật khẩu mới"

### Test Case 4: Mật khẩu tạm hết hạn

**Điều kiện:**
- Đã quá 2 phút kể từ khi nhận mật khẩu tạm

**Các bước:**
1. Đợi 2 phút sau khi nhận email
2. Thử đăng nhập bằng mật khẩu tạm

**Kết quả mong đợi:**
- ❌ Hiển thị lỗi: "Mật khẩu tạm đã hết hạn"

### Test Case 5: Đổi mật khẩu thành công

**Điều kiện:**
- Đã đăng nhập bằng mật khẩu tạm

**Các bước:**
1. Nhập mật khẩu mới: `NewPass123`
2. Xác nhận mật khẩu: `NewPass123`
3. Nhấn "Xác Nhận Đổi Mật Khẩu"

**Kết quả mong đợi:**
- ✅ Đổi mật khẩu thành công
- ✅ Redirect về trang chính
- ✅ Temp password bị xóa khỏi database
- ✅ Lần đăng nhập sau phải dùng mật khẩu mới

### Test Case 6: Vẫn đăng nhập được bằng mật khẩu chính

**Điều kiện:**
- Đã tạo mật khẩu tạm nhưng vẫn nhớ mật khẩu chính

**Các bước:**
1. Truy cập trang login
2. Nhập username và mật khẩu chính (không phải temp password)
3. Nhấn "Đăng nhập"

**Kết quả mong đợi:**
- ✅ Đăng nhập thành công bằng mật khẩu chính
- ✅ KHÔNG yêu cầu đổi mật khẩu
- ✅ Redirect trực tiếp về trang chính

---

## 🐛 XỬ LÝ LỖI

### Lỗi 1: "Không thể kết nối đến dịch vụ email"

**Nguyên nhân:**
- n8n không chạy hoặc webhook URL sai
- Network timeout

**Giải pháp:**
1. Kiểm tra n8n đã chạy chưa:
   ```bash
   curl http://localhost:5678/webhook/forgot-password
   ```
2. Kiểm tra URL trong `app.py` có đúng không
3. Restart n8n workflow

### Lỗi 2: Email không được gửi

**Nguyên nhân:**
- Gmail credentials chưa được cấu hình
- Gmail OAuth token hết hạn

**Giải pháp:**
1. Vào n8n → Node "Send Forgot Password Email"
2. Re-authenticate Gmail credentials
3. Test lại workflow

### Lỗi 3: "Mật khẩu phải có ít nhất 8 ký tự"

**Nguyên nhân:**
- Mật khẩu mới không đáp ứng yêu cầu

**Giải pháp:**
- Đảm bảo mật khẩu mới:
  - Ít nhất 8 ký tự
  - Có chữ hoa
  - Có chữ thường
  - Có chữ số

### Lỗi 4: Database schema chưa được update

**Nguyên nhân:**
- Chưa chạy SQL script trong Supabase

**Giải pháp:**
1. Truy cập Supabase Dashboard
2. SQL Editor → Paste toàn bộ `forgot_password_schema.sql`
3. Run query
4. Kiểm tra bằng:
   ```sql
   SELECT * FROM users LIMIT 1;
   ```
   Phải thấy các cột mới: `temp_password`, `temp_password_expires_at`, `require_password_change`

---

## 📊 KIẾN TRÚC HỆ THỐNG

```
┌─────────────┐
│   User      │
│  Browser    │
└──────┬──────┘
       │
       │ 1. Nhấn "Quên mật khẩu"
       │
       ▼
┌──────────────────┐
│  Flask App       │
│  /forgot-password│
└──────┬───────────┘
       │
       │ 2. Tạo temp password
       │    Hash & lưu vào DB
       │
       ▼
┌──────────────────┐
│   Supabase DB    │
│   users table    │
└──────┬───────────┘
       │
       │ 3. Gửi email data
       │
       ▼
┌──────────────────┐
│   n8n Webhook    │
│  forgot-password │
└──────┬───────────┘
       │
       │ 4. Generate HTML email
       │
       ▼
┌──────────────────┐
│  Gmail API       │
│  Send Email      │
└──────┬───────────┘
       │
       │ 5. Email delivered
       │
       ▼
┌──────────────────┐
│   User Email     │
│  (Temp Password) │
└──────────────────┘
```

---

## 📁 CẤU TRÚC FILE

```
file-transfer-system/
├── database/
│   └── forgot_password_schema.sql      # SQL script cho Supabase
│
├── n8n/
│   └── forgot_password_email_workflow.json  # n8n workflow
│
├── web/
│   ├── app.py                          # Flask routes (đã cập nhật)
│   │
│   ├── services/
│   │   └── user_service.py             # User service (đã cập nhật)
│   │
│   └── templates/
│       ├── login.html                  # Trang login (đã cập nhật)
│       └── force_change_password.html  # Trang đổi mật khẩu (MỚI)
│
└── HUONG_DAN_QUEN_MAT_KHAU.md         # File này
```

---

## 🔧 CẤU HÌNH NÂNG CAO

### Thay đổi thời gian hết hạn mật khẩu tạm

Mặc định: **2 phút**

**Trong `web/services/user_service.py`:**
```python
# Dòng 464
expires_at = (datetime.now() + timedelta(minutes=2)).isoformat()
```

Thay đổi `minutes=2` thành giá trị mong muốn (ví dụ: `minutes=5` cho 5 phút).

**Lưu ý:** Cũng cần cập nhật trong `web/app.py`:
```python
# Dòng 246
"expires_in_minutes": 2
```

### Thay đổi độ dài mật khẩu tạm

Mặc định: **8 ký tự** (3 uppercase + 3 lowercase + 2 digits)

**Trong `web/services/user_service.py`:**
```python
# Dòng 429-431
uppercase = ''.join(random.choices(string.ascii_uppercase, k=3))
lowercase = ''.join(random.choices(string.ascii_lowercase, k=3))
numbers = ''.join(random.choices(string.digits, k=2))
```

Thay đổi tham số `k=` để điều chỉnh số lượng ký tự mỗi loại.

### Tùy chỉnh email template

Email template nằm trong `n8n/forgot_password_email_workflow.json`, node "Code - Forgot Password Email".

Bạn có thể chỉnh sửa:
- Màu sắc (gradient, colors)
- Nội dung text
- Logo/icon
- Layout

Sau khi chỉnh sửa, re-import workflow vào n8n.

---

## 📞 HỖ TRỢ

Nếu gặp vấn đề khi triển khai, vui lòng:

1. Kiểm tra logs:
   - Flask: Terminal chạy `python app.py`
   - n8n: Terminal chạy `n8n start`
   - Supabase: Dashboard → Logs

2. Kiểm tra database:
   ```sql
   -- Xem user có temp password không
   SELECT username, email,
          temp_password IS NOT NULL as has_temp_pwd,
          temp_password_expires_at,
          require_password_change
   FROM users
   WHERE email = 'your-email@example.com';
   ```

3. Test n8n workflow trực tiếp từ n8n dashboard

---

## ✅ CHECKLIST TRIỂN KHAI

- [ ] Chạy SQL script `forgot_password_schema.sql` trong Supabase
- [ ] Import n8n workflow `forgot_password_email_workflow.json`
- [ ] Cấu hình Gmail credentials trong n8n
- [ ] Activate n8n workflow
- [ ] Cập nhật webhook URL trong `app.py`
- [ ] Cài đặt dependencies Python (`requests`, `bcrypt`, `supabase`)
- [ ] Khởi động n8n
- [ ] Khởi động Flask app
- [ ] Test flow từ đầu đến cuối

---

## 🎉 HOÀN THÀNH

Chúc mừng! Bạn đã triển khai thành công tính năng Quên Mật Khẩu với:
- ✅ UI/UX đẹp và responsive
- ✅ Bảo mật tốt (hash, expire, force change)
- ✅ Email template chuyên nghiệp
- ✅ Trải nghiệm người dùng mượt mà

**Developed by:** Claude Code Assistant
**Date:** 2025-01-15
**Version:** 1.0
