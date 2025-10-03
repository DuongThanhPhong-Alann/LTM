import bcrypt
from datetime import datetime
import os

class UserService:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        
    def _hash_password(self, password):
        """Mã hóa mật khẩu sử dụng bcrypt"""
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
        
    def _verify_password(self, password, hashed):
        """Kiểm tra mật khẩu với hash đã lưu"""
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
        
    def register(self, username, password):
        """Đăng ký tài khoản mới"""
        try:
            response = self.supabase.table("users").select("*").eq("username", username).execute()
            
            if response.data:
                return False
                
            hashed_password = self._hash_password(password)
            
            self.supabase.table("users").insert({
                "username": username,
                "password": hashed_password,
                "role": "user",
                "is_online": False,
                "last_seen": datetime.now().isoformat()
            }).execute()
            
            return True
        except Exception as e:
            print(f"Lỗi khi đăng ký: {str(e)}")
            return False
            
    def login(self, username, password):
        """Đăng nhập và trả về thông tin user nếu thành công"""
        try:
            response = self.supabase.table("users").select("*").eq("username", username).execute()
            
            if not response.data:
                return None
                
            user = response.data[0]
            if not self._verify_password(password, user['password']):
                return None
            
            # Cập nhật trạng thái online khi đăng nhập
            self.update_last_seen(user['userid'])
                
            return user
        except Exception as e:
            print(f"Lỗi khi đăng nhập: {str(e)}")
            return None
            
    def change_password(self, username, current_password, new_password):
        """Đổi mật khẩu"""
        try:
            response = self.supabase.table("users").select("*").eq("username", username).execute()
            
            if not response.data:
                return False
                
            if not self._verify_password(current_password, response.data[0]['password']):
                return False
                
            hashed_new_password = self._hash_password(new_password)
            self.supabase.table("users").update({"password": hashed_new_password}).eq("username", username).execute()
            return True
        except Exception as e:
            print(f"Lỗi khi đổi mật khẩu: {str(e)}")
            return False
    
    def update_last_seen(self, userid):
        """Cập nhật thời gian hoạt động cuối"""
        try:
            self.supabase.table('users').update({
                'last_seen': datetime.now().isoformat(),
                'is_online': True
            }).eq('userid', userid).execute()
            return True
        except Exception as e:
            print(f"Lỗi khi cập nhật last_seen: {str(e)}")
            return False
    
    def set_offline(self, userid):
        """Đặt trạng thái offline"""
        try:
            self.supabase.table('users').update({
                'is_online': False
            }).eq('userid', userid).execute()
            return True
        except Exception as e:
            print(f"Lỗi khi set offline: {str(e)}")
            return False
    
    def get_user_profile(self, username):
        """Lấy thông tin profile đầy đủ"""
        try:
            result = self.supabase.table('users').select('*').eq('username', username).execute()
            if result.data:
                user = result.data[0]
                user['activity_status'] = self._get_activity_status(user.get('last_seen'), user.get('is_online'))
                return user
            return None
        except Exception as e:
            print(f"Lỗi khi lấy profile: {str(e)}")
            return None
    
    def get_user_by_id(self, userid):
        """Lấy thông tin user theo userid"""
        try:
            result = self.supabase.table('users').select('*').eq('userid', userid).execute()
            if result.data:
                user = result.data[0]
                user['activity_status'] = self._get_activity_status(user.get('last_seen'), user.get('is_online'))
                return user
            return None
        except Exception as e:
            print(f"Lỗi khi lấy user by id: {str(e)}")
            return None
    
    def update_profile(self, userid, data):
        """Cập nhật thông tin profile"""
        try:
            allowed_fields = ['bio', 'phone']
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                return False
                
            result = self.supabase.table('users').update(update_data).eq('userid', userid).execute()
            return bool(result.data)
        except Exception as e:
            print(f"Lỗi khi update profile: {str(e)}")
            return False
    
    def upload_avatar(self, userid, file_data, filename):
        """Upload ảnh đại diện"""
        try:
            ext = os.path.splitext(filename)[1]
            avatar_filename = f"avatar_{userid}_{int(datetime.now().timestamp())}{ext}"
            
            # Xóa avatar cũ nếu có
            try:
                old_user = self.get_user_by_id(userid)
                if old_user and old_user.get('avatar_url'):
                    old_filename = old_user['avatar_url'].split('/')[-1]
                    self.supabase.storage.from_('avatars').remove([old_filename])
            except:
                pass
            
            # Upload file mới
            result = self.supabase.storage.from_('avatars').upload(
                avatar_filename,
                file_data,
                file_options={"content-type": "image/jpeg"}
            )
            
            if result:
                # Lấy public URL
                avatar_url = self.supabase.storage.from_('avatars').get_public_url(avatar_filename)
                
                # Cập nhật avatar_url trong database
                self.supabase.table('users').update({
                    'avatar_url': avatar_url
                }).eq('userid', userid).execute()
                
                return avatar_url
            return None
        except Exception as e:
            print(f"Lỗi khi upload avatar: {str(e)}")
            return None
    
    def _get_activity_status(self, last_seen, is_online):
        """Tính toán trạng thái hoạt động"""
        if not last_seen:
            return "Chưa hoạt động"
        
        if is_online:
            return "Đang hoạt động"
        
        try:
            last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
            diff = datetime.now().astimezone() - last_seen_dt.astimezone()
            minutes = int(diff.total_seconds() / 60)
            
            if minutes < 1:
                return "Vừa xong"
            elif minutes < 5:
                return f"Hoạt động {minutes} phút trước"
            elif minutes < 60:
                return f"Hoạt động {minutes} phút trước"
            elif minutes < 1440:
                hours = minutes // 60
                return f"Hoạt động {hours} giờ trước"
            else:
                days = minutes // 1440
                return f"Hoạt động {days} ngày trước"
        except:
            return "Không rõ"
    
    def get_online_users(self):
        """Lấy danh sách users đang online"""
        try:
            result = self.supabase.table('users').select('userid,username,avatar_url,is_online').eq('is_online', True).execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Lỗi khi lấy online users: {str(e)}")
            return []