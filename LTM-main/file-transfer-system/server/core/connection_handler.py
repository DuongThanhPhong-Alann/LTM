import logging
from .. import config
from . import command_processor
import socket  # Thêm dòng này
from ..services.session_service import session_service
import ssl

logger = logging.getLogger(__name__)


def handle_client(client_socket, client_address):
    """
    Hàm chính để xử lý một kết nối client trong một luồng riêng.
    """
    logger.info(f"[KẾT NỐI MỚI] {client_address} đã kết nối.")

    buffer = ""
    try:
        while True:  # Vòng lặp để xử lý nhiều lệnh từ client
            try:
                data = client_socket.recv(config.BUFFER_SIZE).decode("utf-8")
                if not data:
                    break  # Client đã ngắt kết nối

                buffer += data
                while "\n" in buffer:
                    command_str, buffer = buffer.split("\n", 1)
                    if not command_str.strip():
                        continue

                    logger.debug(f"Nhận từ {client_address}: {command_str}")
                    response = command_processor.process_command(
                        command_str, client_socket, client_address
                    )

                    if response:
                        client_socket.sendall((response + "\n").encode("utf-8"))
            except ssl.SSLError as e:
                logger.error(f"Lỗi SSL trong khi xử lý client {client_address}: {e}")
                break  # Thoát vòng lặp khi có lỗi SSL
            except Exception as e:
                logger.error(
                    f"Lỗi không mong muốn khi xử lý client {client_address}: {e}",
                    exc_info=True,
                )
                break  # Thoát vòng lặp khi có lỗi không mong muốn

    except (ConnectionResetError, ConnectionAbortedError):
        logger.warning(f"[MẤT KẾT NỐI] {client_address} đã ngắt kết nối đột ngột.")
    finally:
        # Đảm bảo thực hiện SSL shutdown trước khi đóng socket nếu là SSLSocket
        if isinstance(client_socket, ssl.SSLSocket):
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
            except OSError as e:
                logger.debug(
                    f"Lỗi khi thực hiện SSL shutdown cho {client_address}: {e}"
                )
        logger.info(f"[ĐÓNG KẾT NỐI] {client_address}.")
        session_service.remove_session(client_address)
        client_socket.close()
