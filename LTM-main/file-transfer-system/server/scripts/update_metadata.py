from supabase import create_client
import os
from datetime import datetime

# Cấu hình Supabase
SUPABASE_URL = "https://qrzycoatheltpfiztkeh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFyenljb2F0aGVsdHBmaXp0a2VoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODY3NjA1NiwiZXhwIjoyMDc0MjUyMDU2fQ.3JmRXRDs-QcEQDHNghjTJEPvoEHA3Zx5MpioHTh9rWM"
STORAGE_BUCKET = "files"

def update_metadata():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    try:
        # Lấy danh sách file
        files = supabase.storage.from_(STORAGE_BUCKET).list()
        
        for file in files:
            filename = file['name']
            # Tạo metadata cơ bản cho file
            metadata = {
                "encrypted": "false",  # Đặt là false vì file cũ chưa được mã hóa
                "original_size": file.get('metadata', {}).get('size', 'N/A'),
                "uploaded_by": "system",  # Đặt là system vì không biết ai upload
                "uploaded_at": datetime.now().isoformat(),
                "original_filename": filename,
                "content_type": file.get('metadata', {}).get('mimetype', 'application/octet-stream')
            }
            
            # Lưu metadata vào bảng files_metadata
            try:
                supabase.table("files_metadata").upsert({
                    "filename": filename,
                    "metadata": metadata
                }).execute()
                print(f"✓ Đã cập nhật metadata cho file: {filename}")
            except Exception as e:
                print(f"✗ Lỗi khi cập nhật metadata cho file {filename}: {str(e)}")
                
    except Exception as e:
        print(f"✗ Lỗi khi lấy danh sách file: {str(e)}")

if __name__ == "__main__":
    print("=== CẬP NHẬT METADATA CHO FILES ===")
    update_metadata()
    print("=== HOÀN THÀNH ===")