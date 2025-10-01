import bcrypt

class UserService:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        
    def _hash_password(self, password):
        """Mã hóa mật khẩu sử dụng bcrypt"""
        # Encode password thành bytes
        password_bytes = password.encode('utf-8')
        # Tạo salt và hash password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        # Trả về hash dạng string để lưu vào database
        return hashed.decode('utf-8')
        
    def _verify_password(self, password, hashed):
        """Kiểm tra mật khẩu với hash đã lưu"""
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
        
    def register(self, username, password):
        """Đăng ký tài khoản mới"""
        try:
            # Kiểm tra username đã tồn tại chưa
            response = self.supabase.table("users").select("*").eq("username", username).execute()
            
            if response.data:
                return False
                
            # Mã hóa mật khẩu trước khi lưu
            hashed_password = self._hash_password(password)
            
            # Tạo user mới với mật khẩu đã mã hóa
            self.supabase.table("users").insert({
                "username": username,
                "password": hashed_password,
                "role": "user"  # Mặc định là user thường
            }).execute()
            
            return True
        except Exception as e:
            print(f"Lỗi khi đăng ký: {str(e)}")
            return False
            
    def login(self, username, password):
        """Đăng nhập và trả về thông tin user nếu thành công"""
        try:
            # Kiểm tra username và password
            response = self.supabase.table("users").select("*").eq("username", username).execute()
            
            if not response.data:
                return None
                
            user = response.data[0]
            # Kiểm tra mật khẩu với hash đã lưu
            if not self._verify_password(password, user['password']):
                return None
                
            return user
        except Exception as e:
            print(f"Lỗi khi đăng nhập: {str(e)}")
            return None
            
    def change_password(self, username, current_password, new_password):
        """Đổi mật khẩu"""
        try:
            # Kiểm tra username và mật khẩu hiện tại
            response = self.supabase.table("users").select("*").eq("username", username).execute()
            
            if not response.data:
                return False
                
            # Xác thực mật khẩu hiện tại
            if not self._verify_password(current_password, response.data[0]['password']):
                return False
                
            # Mã hóa và cập nhật mật khẩu mới
            hashed_new_password = self._hash_password(new_password)
            self.supabase.table("users").update({"password": hashed_new_password}).eq("username", username).execute()
            return True
        except Exception as e:
            print(f"Lỗi khi đổi mật khẩu: {str(e)}")
            return False