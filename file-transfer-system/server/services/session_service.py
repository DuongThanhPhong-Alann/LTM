import threading


class SessionService:
    """
    Quản lý các phiên đăng nhập của người dùng.
    Lớp này là thread-safe (an toàn khi nhiều luồng cùng truy cập).
    """

    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def add_session(self, username, client_address, role):
        """Thêm một phiên đăng nhập mới."""
        with self._lock:
            self._sessions[client_address] = {"username": username, "role": role}

    def remove_session(self, client_address):
        """Xóa một phiên đăng nhập khi client ngắt kết nối."""
        with self._lock:
            if client_address in self._sessions:
                del self._sessions[client_address]

    def get_session_info(self, client_address):
        """Lấy thông tin của một phiên (username, role)."""
        with self._lock:
            return self._sessions.get(client_address)

    def get_session_count(self):
        """Trả về số lượng phiên đang hoạt động."""
        with self._lock:
            return len(self._sessions)


# Tạo một instance duy nhất để sử dụng trên toàn server
session_service = SessionService()
