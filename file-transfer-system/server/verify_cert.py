import ssl
import os

# Lấy đường dẫn tuyệt đối của thư mục chứa file này ('sever')
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_FILE = os.path.join(SERVER_DIR, "security", "certs", "server.crt")
KEY_FILE = os.path.join(SERVER_DIR, "security", "certs", "server.key")

print(f"Đang kiểm tra file cert: {CERT_FILE}")
print(f"Đang kiểm tra file key: {KEY_FILE}")

has_error = False
if not os.path.exists(CERT_FILE) or os.path.getsize(CERT_FILE) == 0:
    print("LỖI: File server.crt không tồn tại hoặc bị trống (0 bytes)!")
    has_error = True

if not os.path.exists(KEY_FILE) or os.path.getsize(KEY_FILE) == 0:
    print("LỖI: File server.key không tồn tại hoặc bị trống (0 bytes)!")
    has_error = True

if not has_error:
    try:
        print("\nĐang thử tải chứng chỉ và khóa...")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
        print("\nTHÀNH CÔNG! Python có thể đọc được file chứng chỉ và khóa.")
        print("=> Vấn đề có thể không nằm ở file cert/key.")
    except Exception as e:
        print(f"\nTHẤT BẠI! Python không thể đọc được file.")
        print(f"Lỗi chi tiết: {e}")
        print(
            "\n=> Vui lòng xóa 2 file .crt và .key và tạo lại chúng bằng script Python đã được cung cấp trước đó."
        )
else:
    print("\n--- HƯỚNG DẪN SỬA LỖI ---")
    print("Chạy lệnh sau từ thư mục gốc của dự án để tạo lại file chứng chỉ:")
    print("python -m sever.security.generate_cert")
