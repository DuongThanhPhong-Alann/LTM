# Các hằng số cấu hình cho server
import os

# Lấy đường dẫn tuyệt đối của thư mục chứa file config này (thư mục 'sever')
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))

HOST = "0.0.0.0"
PORT = 9999
BUFFER_SIZE = 4096  # Kích thước bộ đệm 4KB

# Thư mục
# Sử dụng os.path.join để tạo đường dẫn an toàn và tương thích với mọi HĐH
STORAGE_DIR = os.path.join(SERVER_DIR, "storage")
LOG_FILE = os.path.join(SERVER_DIR, "logs", "server.log")
USER_DATA_FILE = os.path.join(SERVER_DIR, "data", "users.json")

# URL Webhook của N8N (sẽ được Người 3 cung cấp)
N8N_UPLOAD_WEBHOOK = "YOUR_N8N_UPLOAD_WEBHOOK_URL"
N8N_DOWNLOAD_WEBHOOK = "YOUR_N8N_DOWNLOAD_WEBHOOK_URL"
N8N_DELETE_WEBHOOK = "YOUR_N8N_DELETE_WEBHOOK_URL"

## Cấu hình Supabase
SUPABASE_URL = "https://qrzycoatheltpfiztkeh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFyenljb2F0aGVsdHBmaXp0a2VoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODY3NjA1NiwiZXhwIjoyMDc0MjUyMDU2fQ.3JmRXRDs-QcEQDHNghjTJEPvoEHA3Zx5MpioHTh9rWM"
STORAGE_BUCKET = "files"  # Tên bucket lưu trữ file
# Bảo mật
USE_SSL = True  # Đặt thành True để bật mã hóa SSL/TLS
CERT_FILE = os.path.join(SERVER_DIR, "security", "certs", "server.crt")
KEY_FILE = os.path.join(SERVER_DIR, "security", "certs", "server.key")
