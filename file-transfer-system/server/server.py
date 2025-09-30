import socket
import threading
import logging
import os
import ssl
from . import config
from .core.connection_handler import handle_client


def setup_logging():
    """Cấu hình hệ thống logging."""
    # This setup is more robust for handling Unicode characters on different platforms,
    # especially on Windows where the default console encoding might not be UTF-8.
    log_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear any existing handlers to avoid duplicate logs
    root_logger.handlers.clear()

    # File handler with UTF-8 encoding to correctly write logs with Vietnamese characters
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
    file_handler = logging.FileHandler(config.LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

    # Console/Stream handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)
    root_logger.addHandler(stream_handler)


def setup_directories():
    """Tạo các thư mục cần thiết nếu chưa có."""
    os.makedirs(config.STORAGE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(config.USER_DATA_FILE), exist_ok=True)


def main():
    """Hàm chính khởi động server."""
    setup_logging()
    setup_directories()
    logger = logging.getLogger(__name__)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    ssl_context = None
    if config.USE_SSL:
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(
                certfile=config.CERT_FILE, keyfile=config.KEY_FILE
            )
            logger.info("SSL/TLS được kích hoạt.")
        except (ssl.SSLError, FileNotFoundError, OSError) as e:
            logger.error(
                f"Lỗi khi tải chứng chỉ SSL: {e}. Server sẽ chạy không mã hóa."
            )
            ssl_context = None

    server_socket.bind((config.HOST, config.PORT))
    server_socket.listen(5)
    logger.info(f"[*] Server đang lắng nghe trên {config.HOST}:{config.PORT}")

    try:
        while True:
            client_socket, client_address = server_socket.accept()

            if ssl_context:
                conn = ssl_context.wrap_socket(client_socket, server_side=True)
                try:
                    # Thực hiện handshake SSL/TLS ngay lập tức
                    conn.do_handshake()
                except ssl.SSLError as e:
                    logger.error(f"SSL Handshake thất bại cho {client_address}: {e}")
                    client_socket.close()  # Đóng socket thô nếu handshake thất bại
                    continue  # Bỏ qua client này và chờ kết nối mới
            else:
                conn = client_socket

            thread = threading.Thread(target=handle_client, args=(conn, client_address))
            thread.daemon = True
            thread.start()
            logger.info(f"[TỔNG SỐ CLIENT] {threading.active_count() - 1}")

    except KeyboardInterrupt:
        logger.info("[*] Server đang tắt...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
