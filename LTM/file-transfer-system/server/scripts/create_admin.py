from supabase import create_client

# Cấu hình Supabase
SUPABASE_URL = "https://qrzycoatheltpfiztkeh.supabase.co"
# Sử dụng service_role key thay vì anon key
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFyenljb2F0aGVsdHBmaXp0a2VoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODY3NjA1NiwiZXhwIjoxNzU4Njc2MDU2fQ.rtpP1wfhHRoSJmA1pN5slZGdsWbpKpIZ43l2eNv0vCA"

def create_admin_user():
    # Khởi tạo Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Tạo user admin
    try:
        # Kiểm tra xem admin đã tồn tại chưa
        response = supabase.table('users').select("*").eq('username', 'admin').execute()
        
        if response.data:
            print("✗ Tài khoản admin đã tồn tại!")
            return
            
        # Thêm tài khoản admin
        data = {
            'username': 'admin',
            'password': 'admin',
            'role': 'admin'
        }
        
        response = supabase.table('users').insert(data).execute()
        print("✓ Đã tạo tài khoản admin thành công!")
        
    except Exception as e:
        print(f"✗ Lỗi: {str(e)}")

if __name__ == "__main__":
    print("=== TẠO TÀI KHOẢN ADMIN ===")
    create_admin_user()