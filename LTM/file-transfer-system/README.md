# Đề tài: Hệ thống Quản lý & Truyền File qua Mạng tích hợp N8N

Dự án xây dựng một hệ thống client-server cho phép truyền file qua mạng TCP, tích hợp với N8N để tự động hóa các quy trình sao lưu, thông báo và ghi log.

## Mục tiêu

- Xây dựng hệ thống client-server cho phép upload/download file qua mạng.
- Quản lý người dùng (đăng nhập, phân quyền).
- Tích hợp với N8N để tự động hóa các tác vụ.

## Cấu trúc dự án

- **/client**: Mã nguồn cho ứng dụng client.
- **/server**: Mã nguồn cho ứng dụng server.
- **/docs**: Tài liệu dự án, kịch bản demo, sơ đồ.

## Hướng dẫn cài đặt

1. Clone repository về máy.
2. Cài đặt các thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
   ```
3. Tạo chứng chỉ SSL cho server (chạy lần đầu):
   ```bash
   python -m server.security.cert
   ```
4. Khởi động server:
   ```bash
   python -m server.server
   ```