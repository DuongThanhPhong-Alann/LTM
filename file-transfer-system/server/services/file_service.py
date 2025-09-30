import os
import logging
from .. import config

logger = logging.getLogger(__name__)


def list_files():
    """Trả về danh sách các file trong thư mục lưu trữ."""
    try:
        return os.listdir(config.STORAGE_DIR)
    except FileNotFoundError:
        logger.error(f"Thư mục lưu trữ không tồn tại: {config.STORAGE_DIR}")
        return []


def receive_file(client_socket, filename, filesize):
    """Nhận file từ client và lưu vào thư mục storage."""
    filepath = os.path.join(
        config.STORAGE_DIR, os.path.basename(filename)
    )  # Chống path traversal
    try:
        bytes_received = 0
        with open(filepath, "wb") as f:
            while bytes_received < filesize:
                chunk = client_socket.recv(config.BUFFER_SIZE)
                if not chunk:
                    raise ConnectionError("Kết nối bị mất trong khi nhận file.")
                f.write(chunk)
                bytes_received += len(chunk)

        logger.info(f"Nhận thành công file: {filename} ({filesize} bytes)")
        return True

    except Exception as e:
        logger.error(f"Lỗi khi nhận file {filename}: {e}")
        if os.path.exists(filepath):
            os.remove(filepath)  # Xóa file bị lỗi
        return False


def send_file(client_socket, filename):
    """Gửi file từ server đến client."""
    filepath = os.path.join(config.STORAGE_DIR, os.path.basename(filename))
    if not os.path.exists(filepath):
        logger.warning(f"Yêu cầu tải file không tồn tại: {filename}")
        return False

    try:
        filesize = os.path.getsize(filepath)
        # Báo cho client biết file tồn tại và kích thước của nó
        client_socket.sendall(f"READY {filesize}\n".encode("utf-8"))

        with open(filepath, "rb") as f:
            while chunk := f.read(config.BUFFER_SIZE):
                client_socket.sendall(chunk)
        logger.info(f"Gửi thành công file: {filename}")
        return True
    except Exception as e:
        logger.error(f"Lỗi khi gửi file {filename}: {e}")
        return False


def delete_file(filename, user_role):
    """Xóa một file trong thư mục lưu trữ. Chỉ admin mới có quyền."""
    # Phân quyền: chỉ có 'admin' mới được xóa
    if user_role != "admin":
        logger.warning(
            f"User với quyền '{user_role}' đã cố gắng xóa file '{filename}'. Bị từ chối."
        )
        return False

    filepath = os.path.join(config.STORAGE_DIR, os.path.basename(filename))
    if not os.path.exists(filepath):
        logger.warning(f"Yêu cầu xóa file không tồn tại: {filename}")
        return False
    try:
        os.remove(filepath)
        logger.info(f"Admin đã xóa thành công file: {filename}")
        return True
    except Exception as e:
        logger.error(f"Lỗi khi xóa file {filename}: {e}")
        return False
