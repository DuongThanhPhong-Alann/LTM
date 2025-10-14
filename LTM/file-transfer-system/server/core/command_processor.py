import logging
from ..services import user_service, file_service, n8n_service
from ..services.session_service import session_service

logger = logging.getLogger(__name__)


def process_command(command_str, client_socket, client_address):
    """
    Phân tích và xử lý lệnh từ client.
    Trả về một chuỗi phản hồi để gửi lại cho client.
    """
    parts = command_str.strip().split(" ", 1)
    command = parts[0].upper() if parts else ""
    args_str = parts[1] if len(parts) > 1 else ""

    # Các lệnh không yêu cầu đăng nhập
    if command == "LOGIN":
        try:
            username, password = args_str.split(" ", 1)
            try:
                role = user_service.authenticate_user(username, password)
                if role:
                    session_service.add_session(username, client_address, role)
                    logger.info(f"User '{username}' đăng nhập từ {client_address}")
                    return f"OK Login successful. Role: {role}"
                else:
                    logger.warning(
                        f"Đăng nhập thất bại cho user '{username}' từ {client_address}"
                    )
                    return "ERROR Invalid credentials"
            except Exception as e:
                logger.error(
                    f"Lỗi nghiêm trọng trong quá trình xác thực user '{username}': {e}"
                )
                return "ERROR Server error during authentication"
        except ValueError:
            return "ERROR Usage: LOGIN <username> <password>"

    # Các lệnh sau đây yêu cầu phải đăng nhập
    session_info = session_service.get_session_info(client_address)
    if not session_info:
        return "ERROR Not logged in"

    username = session_info["username"]

    if command == "LIST":
        files = file_service.list_files()
        return f"OK {len(files)}\n" + "\n".join(files)

    elif command == "UPLOAD":
        try:
            filename, filesize_str = args_str.split(" ", 1)
            filesize = int(filesize_str)
            # Báo cho client sẵn sàng nhận file
            client_socket.sendall(b"READY\n")

            if file_service.receive_file(client_socket, filename, filesize):
                # Tạm thời vô hiệu hóa việc gửi thông báo N8N
                # try:
                #     n8n_service.notify_upload(username, filename, filesize)
                # except Exception as e:
                #     logger.error(f"Lỗi khi gửi thông báo N8N cho UPLOAD: {e}")
                client_socket.sendall(
                    f"OK File '{filename}' uploaded\n".encode("utf-8")
                )
                return None  # Giao tiếp đã hoàn tất, không cần gửi thêm
            else:
                client_socket.sendall(
                    f"ERROR Failed to upload '{filename}'\n".encode("utf-8")
                )
                return None  # Giao tiếp đã hoàn tất, không cần gửi thêm
        except (ValueError, IndexError):
            return "ERROR Usage: UPLOAD <filename> <filesize>"

    elif command == "DOWNLOAD":
        filename = args_str
        if not filename:
            return "ERROR Usage: DOWNLOAD <filename>"

        # file_service.send_file sẽ xử lý việc gửi phản hồi READY hoặc lỗi
        if file_service.send_file(client_socket, filename):
            # Tạm thời vô hiệu hóa việc gửi thông báo N8N
            # try:
            #     n8n_service.notify_download(username, filename)
            # except Exception as e:
            #     logger.error(f"Lỗi khi gửi thông báo N8N cho DOWNLOAD: {e}")
            return None  # Không cần gửi phản hồi text vì đã gửi file
        else:
            return "ERROR File not found or error sending"

    elif command == "LOGOUT":
        session_service.remove_session(client_address)
        logger.info(f"User '{username}' đã đăng xuất.")
        return "OK Logged out"

    elif command == "DELETE":
        filename = args_str
        if not filename:
            return "ERROR Usage: DELETE <filename>"

        if file_service.delete_file(filename, session_info.get("role")):
            # Tạm thời vô hiệu hóa việc gửi thông báo N8N
            # try:
            #     n8n_service.notify_delete(username, filename)
            # except Exception as e:
            #     logger.error(f"Lỗi khi gửi thông báo N8N cho DELETE: {e}")
            return f"OK File '{filename}' deleted"
        else:
            return f"ERROR File not found or permission denied"

    elif command == "STATUS":
        if session_info.get("role") != "admin":
            return "ERROR Permission denied. Admin only."

        count = session_service.get_session_count()
        return f"OK {count} user(s) online."

    else:
        return "ERROR Unknown command"
