-- Kiểm tra xem database 'file_transfer_db' đã tồn tại chưa
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'file_transfer_db')
BEGIN
    -- Nếu chưa tồn tại, tạo database mới
    CREATE DATABASE file_transfer_db;
    PRINT 'Database "file_transfer_db" đã được tạo.';
END
ELSE
BEGIN
    PRINT 'Database "file_transfer_db" đã tồn tại.';
END
GO

USE file_transfer_db;
GO

-- Tạo bảng Users nếu chưa tồn tại
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Users' and xtype='U')
BEGIN
    CREATE TABLE Users (
        UserID INT PRIMARY KEY IDENTITY(1,1),
        Username NVARCHAR(50) NOT NULL UNIQUE,
        Password NVARCHAR(50) NOT NULL, -- Cảnh báo: Mật khẩu nên được băm (hashed)
        Role NVARCHAR(20) NOT NULL
    );
    PRINT 'Bảng "Users" đã được tạo.';
END
ELSE
BEGIN
    PRINT 'Bảng "Users" đã tồn tại.';
END
GO

-- Thêm dữ liệu người dùng mẫu nếu họ chưa tồn tại
IF NOT EXISTS (SELECT 1 FROM Users WHERE Username = 'admin')
BEGIN
    INSERT INTO Users (Username, Password, Role) VALUES ('admin', 'admin', 'admin');
    PRINT 'Đã thêm người dùng "admin".';
END

IF NOT EXISTS (SELECT 1 FROM Users WHERE Username = 'user')
BEGIN
    INSERT INTO Users (Username, Password, Role) VALUES ('user', 'user', 'user');
    PRINT 'Đã thêm người dùng "user".';
END
GO

PRINT 'Hoàn tất thiết lập cơ sở dữ liệu.';
GO
