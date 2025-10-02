import os
import sys
from supabase import create_client, Client
from pathlib import Path

# Cấu hình Supabase
SUPABASE_URL = "https://qrzycoatheltpfiztkeh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFyenljb2F0aGVsdHBmaXp0a2VoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODY3NjA1NiwiZXhwIjoyMDc0MjUyMDU2fQ.3JmRXRDs-QcEQDHNghjTJEPvoEHA3Zx5MpioHTh9rWM"
STORAGE_BUCKET = "files"  # Tên bucket lưu trữ file

class SupabaseFileClient:
    def __init__(self):
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.user = None
        self.user_role = None

    def login(self, username: str, password: str):
        """Đăng nhập người dùng"""
        try:
            # Xác thực qua bảng users
            response = self.supabase.table("users").select("*").eq("username", username).execute()
            
            if response.data:
                user_data = response.data[0]
                stored_password = user_data.get('password')
                
                if stored_password == password:
                    self.user = user_data
                    self.user_role = user_data.get('Role')
                    print(f"✓ Đăng nhập thành công. Role: {self.user_role}")
                    return True
                else:
                    print("✗ Sai mật khẩu")
                    return False
            else:
                print("✗ Không tìm thấy thông tin người dùng")
                return False
                
        except Exception as e:
            print(f"✗ Đăng nhập thất bại: {str(e)}")
            return False

    def list_files(self):
        """Liệt kê file trong storage"""
        try:
            files = self.supabase.storage.from_(STORAGE_BUCKET).list()
            
            if not files:
                print("Thư mục trên server đang trống.")
            else:
                print("\n--- Danh sách file trên server ---")
                for file in files:
                    size = file.get('metadata', {}).get('size', 0)
                    print(f"- {file['name']} ({size} bytes)")
                print("---------------------------------")
                
        except Exception as e:
            print(f"Lỗi khi lấy danh sách file: {str(e)}")

    def upload_file(self, filepath: str):
        """Upload file lên Supabase Storage"""
        try:
            if not os.path.exists(filepath):
                print(f"✗ File '{filepath}' không tồn tại.")
                return

            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)

            print(f"Đang tải lên: {filename} ({filesize} bytes)...")

            with open(filepath, 'rb') as f:
                # Upload file
                response = self.supabase.storage.from_(STORAGE_BUCKET).upload(
                    path=filename,
                    file=f,
                    file_options={"content-type": "application/octet-stream"}
                )

            print(f"✓ Upload thành công: {filename}")

        except Exception as e:
            print(f"✗ Lỗi upload: {str(e)}")

    def download_file(self, filename: str):
        """Download file từ Supabase Storage"""
        try:
            # Lấy tên file không kèm đường dẫn
            filename = os.path.basename(filename)
            print(f"Đang tải về: {filename}...")

            try:
                # Kiểm tra file có tồn tại không
                files = self.supabase.storage.from_(STORAGE_BUCKET).list()
                file_exists = any(f['name'] == filename for f in files)
                if not file_exists:
                    print(f"✗ File '{filename}' không tồn tại trên server")
                    return
                
                # Tạo signed URL để download
                signed_url = self.supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
                    path=filename,
                    expires_in=3600  # URL có hiệu lực trong 1 giờ
                )
                
                if signed_url and 'signedURL' in signed_url:
                    # Lưu vào thư mục Downloads của Windows
                    download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                    if not os.path.exists(download_dir):
                        # Thử thư mục Download (tiếng Anh)
                        download_dir = os.path.join(os.path.expanduser("~"), "Download")
                        if not os.path.exists(download_dir):
                            print("✗ Không tìm thấy thư mục Downloads")
                            return
                            
                    filepath = os.path.join(download_dir, filename)
                    print(f"Đang lưu file vào: {filepath}")

                    # Download file từ signed URL
                    import requests
                    response = requests.get(signed_url['signedURL'])
                    response.raise_for_status()  # Kiểm tra lỗi HTTP
                    
                    # Lưu file
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    
                    # Kiểm tra file đã được tạo và có nội dung
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                        print(f"✓ Đã tải xong: {filepath}")
                        print(f"  Kích thước file: {os.path.getsize(filepath)} bytes")
                    else:
                        print(f"✗ Lỗi: File không được tạo hoặc rỗng")
                else:
                    print("✗ Không thể tạo URL download")
            
            except requests.RequestException as e:
                print(f"✗ Lỗi khi tải file: {str(e)}")
                
        except Exception as e:
            print(f"✗ Lỗi download: {str(e)}")

    def delete_file(self, filename: str):
        """Xóa file (chỉ admin)"""
        try:
            if self.user_role != 'admin':
                print("✗ Lệnh này chỉ dành cho admin.")
                return

            # Xóa file
            response = self.supabase.storage.from_(STORAGE_BUCKET).remove([filename])
            print(f"✓ Đã xóa file: {filename}")

        except Exception as e:
            print(f"✗ Lỗi xóa file: {str(e)}")

    def get_status(self):
        """Lấy thông tin trạng thái (chỉ admin)"""
        try:
            if self.user_role != 'admin':
                print("✗ Lệnh này chỉ dành cho admin.")
                return

            # Đếm số user trong bảng Users
            users = self.supabase.table("Users").select("*", count='exact').execute()
            print(f"✓ Tổng số người dùng: {users.count}")

        except Exception as e:
            print(f"✗ Lỗi: {str(e)}")

    def logout(self):
        """Đăng xuất"""
        try:
            self.supabase.auth.sign_out()
            print("✓ Đã đăng xuất.")
            return True
        except Exception as e:
            print(f"✗ Lỗi đăng xuất: {str(e)}")
            return False


def print_help(user_role):
    """In trợ giúp"""
    print("\n--- Các lệnh có sẵn ---")
    print("list           - Liệt kê file")
    print("upload <path>  - Upload file")
    print("download <fn>  - Download file")
    if user_role == "admin":
        print("delete <fn>    - Xóa file (admin)")
        print("status         - Xem thống kê (admin)")
    print("logout         - Đăng xuất")
    print("help           - Trợ giúp")
    print("exit           - Thoát")
    print("-----------------------\n")


def main():
    """Hàm chính"""
    client = SupabaseFileClient()

    print("=== SUPABASE FILE TRANSFER CLIENT ===\n")

    # Đăng nhập
    while True:
        username = input("Username: ").strip()
        password = input("Password: ").strip()

        if client.login(username, password):
            break
        
        retry = input("Thử lại? (y/n): ").lower()
        if retry != 'y':
            return

    print_help(client.user_role)

    # Command loop
    while True:
        try:
            command_line = input(f"({client.user_role}) > ").strip()
            
            if not command_line:
                continue

            parts = command_line.split(maxsplit=1)
            command = parts[0].lower()

            if command == "exit":
                break
            elif command == "list":
                client.list_files()
            elif command == "upload":
                if len(parts) > 1:
                    client.upload_file(parts[1])
                else:
                    print("Sử dụng: upload <đường_dẫn_file>")
            elif command == "download":
                if len(parts) > 1:
                    client.download_file(parts[1])
                else:
                    print("Sử dụng: download <tên_file>")
            elif command == "delete":
                if len(parts) > 1:
                    client.delete_file(parts[1])
                else:
                    print("Sử dụng: delete <tên_file>")
            elif command == "status":
                client.get_status()
            elif command == "logout":
                if client.logout():
                    break
            elif command == "help":
                print_help(client.user_role)
            else:
                print("Lệnh không hợp lệ. Gõ 'help' để xem danh sách.")

        except (EOFError, KeyboardInterrupt):
            print("\nĐang thoát...")
            break

    print("Bye!")


if __name__ == "__main__":
    main()