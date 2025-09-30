import logging
from .. import config
from supabase import create_client

logger = logging.getLogger(__name__)

# Khởi tạo Supabase client
supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

def authenticate_user(username, password):
    """
    Xác thực người dùng bằng Supabase.
    Trả về 'role' nếu thành công, None nếu thất bại.
    """
    try:
        # Tìm user trong bảng users của Supabase
        response = supabase.table('users').select('*').eq('username', username).execute()
        
        if response.data:
            user_data = response.data[0]
            stored_password = user_data.get('password')
            role = user_data.get('role')
            
            if stored_password == password:
                logger.info(f"Đăng nhập thành công cho user '{username}' (Supabase).")
                return role
            else:
                logger.warning(f"Đăng nhập thất bại cho user '{username}': Mật khẩu không đúng.")
                return None
        else:
            logger.warning(f"Đăng nhập thất bại: User '{username}' không tồn tại.")
            return None
            
    except Exception as e:
        logger.error(f"Lỗi khi xác thực người dùng '{username}': {e}")
        return None
