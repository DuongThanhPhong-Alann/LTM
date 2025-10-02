import pyodbc
import getpass
from werkzeug.security import generate_password_hash
from . import config
import sys


def add_or_update_user():
    """
    Thêm người dùng mới hoặc cập nhật mật khẩu cho người dùng hiện tại.
    Mật khẩu sẽ được băm (hashed) trước khi lưu.
    """
    try:
        username = input("Nhập tên người dùng (username): ")
        password = getpass.getpass("Nhập mật khẩu: ")
        password_confirm = getpass.getpass("Xác nhận mật khẩu: ")

        if password != password_confirm:
            print("Lỗi: Mật khẩu không khớp.")
            return

        role = input("Nhập vai trò (admin/user): ").lower()
        if role not in ["admin", "user"]:
            print("Lỗi: Vai trò phải là 'admin' hoặc 'user'.")
            return

        # Băm mật khẩu
        hashed_password = generate_password_hash(password)

        with pyodbc.connect(config.SQL_CONNECTION_STRING) as conn:
            cursor = conn.cursor()
            # Kiểm tra xem user đã tồn tại chưa
            cursor.execute("SELECT UserID FROM Users WHERE Username = ?", username)
            user_exists = cursor.fetchone()

            if user_exists:
                # Cập nhật người dùng hiện tại
                print(f"Người dùng '{username}' đã tồn tại. Đang cập nhật mật khẩu...")
                cursor.execute(
                    "UPDATE Users SET Password = ?, Role = ? WHERE Username = ?",
                    hashed_password,
                    role,
                    username,
                )
                print("Cập nhật thành công.")
            else:
                # Thêm người dùng mới
                print(f"Đang thêm người dùng mới '{username}'...")
                cursor.execute(
                    "INSERT INTO Users (Username, Password, Role) VALUES (?, ?, ?)",
                    username,
                    hashed_password,
                    role,
                )
                print("Thêm mới thành công.")

            conn.commit()

    except pyodbc.Error as ex:
        print(f"Lỗi cơ sở dữ liệu: {ex}")
    except Exception as e:
        print(f"Lỗi không mong muốn: {e}")


if __name__ == "__main__":
    add_or_update_user()
