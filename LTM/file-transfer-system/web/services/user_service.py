# services/user_service.py
import bcrypt
from datetime import datetime
import os
import re
import random

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
    
    def validate_email(self, email):
        """Kiểm tra định dạng email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def validate_password(self, password):
        """
        Kiểm tra mật khẩu mạnh:
        - Ít nhất 8 ký tự
        - Có chữ hoa, chữ thường, số
        """
        if len(password) < 8:
            return False, "Mật khẩu phải có ít nhất 8 ký tự"
        
        if not re.search(r'[A-Z]', password):
            return False, "Mật khẩu phải có ít nhất 1 chữ hoa"
        
        if not re.search(r'[a-z]', password):
            return False, "Mật khẩu phải có ít nhất 1 chữ thường"
        
        if not re.search(r'[0-9]', password):
            return False, "Mật khẩu phải có ít nhất 1 chữ số"
        
        return True, "OK"
    
    def generate_otp(self):
        """Tạo mã OTP 6 số"""
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    def create_pending_registration(self, username, email, password):
        """
        Tạo pending registration và trả về OTP code
        Returns: (success, otp_code, message)
        """
        try:
            # Kiểm tra username đã tồn tại
            existing_user = self.supabase.table('users').select('username').eq('username', username).execute()
            if existing_user.data:
                return False, None, "Tên đăng nhập đã tồn tại"
            
            # Kiểm tra email đã tồn tại
            existing_email = self.supabase.table('users').select('email').eq('email', email).execute()
            if existing_email.data:
                return False, None, "Email đã được sử dụng"
            
            # Xóa pending registration cũ nếu có
            self.supabase.table('pending_registrations').delete().eq('email', email).execute()
            self.supabase.table('pending_registrations').delete().eq('username', username).execute()
            
            # Hash password
            hashed_password = self._hash_password(password)
            
            # Tạo OTP
            otp_code = self.generate_otp()
            
            # Tính thời gian hết hạn (15 phút)
            from datetime import timedelta
            expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()
            
            # Lưu vào pending_registrations
            result = self.supabase.table('pending_registrations').insert({
                'username': username,
                'email': email,
                'password': hashed_password,
                'verification_code': otp_code,
                'expires_at': expires_at,
                'verification_attempts': 0
            }).execute()
            
            if result.data:
                return True, otp_code, "OTP đã được tạo"
            else:
                return False, None, "Không thể tạo pending registration"
                
        except Exception as e:
            print(f"Error creating pending registration: {str(e)}")
            return False, None, f"Lỗi: {str(e)}"
    
    def verify_otp(self, email, otp_code):
        """
        Xác thực OTP và tạo user
        Returns: (success, message, username)
        """
        try:
            # Lấy pending registration
            pending = self.supabase.table('pending_registrations').select('*').eq('email', email).execute()
            
            if not pending.data:
                return False, "Mã xác thực không tồn tại hoặc đã hết hạn", None
            
            record = pending.data[0]
            
            # Kiểm tra hết hạn
            expires_at = datetime.fromisoformat(record['expires_at'].replace('Z', '+00:00'))
            if datetime.now().astimezone() > expires_at.astimezone():
                # Xóa record hết hạn
                self.supabase.table('pending_registrations').delete().eq('email', email).execute()
                return False, "Mã xác thực đã hết hạn. Vui lòng đăng ký lại", None
            
            # Kiểm tra số lần thử
            if record['verification_attempts'] >= 3:
                self.supabase.table('pending_registrations').delete().eq('email', email).execute()
                return False, "Đã vượt quá số lần thử. Vui lòng đăng ký lại", None
            
            # Kiểm tra mã OTP
            if record['verification_code'] == otp_code:
                # Tạo user mới
                user_result = self.supabase.table('users').insert({
                    'username': record['username'],
                    'email': record['email'],
                    'password': record['password'],
                    'role': 'user',
                    'is_verified': True,
                    'is_online': False,
                    'last_seen': datetime.now().isoformat()
                }).execute()
                
                if user_result.data:
                    # Xóa pending registration
                    self.supabase.table('pending_registrations').delete().eq('email', email).execute()
                    return True, "Xác thực thành công!", record['username']
                else:
                    return False, "Không thể tạo tài khoản", None
            else:
                # Tăng số lần thử
                attempts = record['verification_attempts'] + 1
                self.supabase.table('pending_registrations').update({
                    'verification_attempts': attempts
                }).eq('email', email).execute()
                
                remaining = 3 - attempts
                return False, f"Mã xác thực không đúng. Còn {remaining} lần thử", None
                
        except Exception as e:
            print(f"Error verifying OTP: {str(e)}")
            return False, f"Lỗi: {str(e)}", None
    
    def resend_otp(self, email):
        """
        Tạo lại OTP mới cho email
        Returns: (success, otp_code, message)
        """
        try:
            # Lấy pending registration
            pending = self.supabase.table('pending_registrations').select('*').eq('email', email).execute()
            
            if not pending.data:
                return False, None, "Không tìm thấy đăng ký chờ xác thực"
            
            # Tạo OTP mới
            new_otp = self.generate_otp()
            
            # Cập nhật OTP và reset attempts
            from datetime import timedelta
            expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()
            
            result = self.supabase.table('pending_registrations').update({
                'verification_code': new_otp,
                'verification_attempts': 0,
                'expires_at': expires_at
            }).eq('email', email).execute()
            
            if result.data:
                return True, new_otp, "OTP mới đã được tạo"
            else:
                return False, None, "Không thể tạo OTP mới"
                
        except Exception as e:
            print(f"Error resending OTP: {str(e)}")
            return False, None, f"Lỗi: {str(e)}"
    
    def cleanup_expired_registrations(self):
        """Xóa các pending registrations đã hết hạn"""
        try:
            now = datetime.now().isoformat()
            result = self.supabase.table('pending_registrations').delete().lt('expires_at', now).execute()
            return True
        except Exception as e:
            print(f"Error cleaning up expired registrations: {str(e)}")
            return False
        
    def register(self, username, password, email=None):
        """
        Đăng ký tài khoản mới (legacy method - không dùng cho email verification)
        Chỉ dùng khi không cần verify email
        """
        try:
            response = self.supabase.table("users").select("*").eq("username", username).execute()
            
            if response.data:
                return False
                
            hashed_password = self._hash_password(password)
            
            data = {
                "username": username,
                "password": hashed_password,
                "role": "user",
                "is_online": False,
                "last_seen": datetime.now().isoformat()
            }
            
            if email:
                data['email'] = email
                data['is_verified'] = False
            
            self.supabase.table("users").insert(data).execute()
            
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
            
            # Kiểm tra tài khoản đã được verify chưa (nếu có email)
            if user.get('email') and not user.get('is_verified', False):
                print(f"Account not verified: {username}")
                return None
            
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