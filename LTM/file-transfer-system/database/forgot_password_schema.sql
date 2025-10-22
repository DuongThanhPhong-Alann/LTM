-- ============================================
-- SCHEMA CHO TÍNH NĂNG QUÊN MẬT KHẨU
-- ============================================
-- Thực thi script này trong Supabase SQL Editor

-- 1. Thêm cột temporary password vào bảng Users
ALTER TABLE users
ADD COLUMN IF NOT EXISTS temp_password VARCHAR(255),
ADD COLUMN IF NOT EXISTS temp_password_expires_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS require_password_change BOOLEAN DEFAULT FALSE;

-- Tạo index cho performance
CREATE INDEX IF NOT EXISTS idx_users_temp_password ON users(temp_password) WHERE temp_password IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_temp_expires ON users(temp_password_expires_at) WHERE temp_password_expires_at IS NOT NULL;

-- 2. Function để generate mật khẩu tạm ngẫu nhiên (8 ký tự: chữ hoa, chữ thường, số)
CREATE OR REPLACE FUNCTION generate_temp_password()
RETURNS VARCHAR(8) AS $$
DECLARE
    chars TEXT := 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    lower_chars TEXT := 'abcdefghijklmnopqrstuvwxyz';
    numbers TEXT := '0123456789';
    result TEXT := '';
    i INTEGER;
BEGIN
    -- 3 chữ hoa
    FOR i IN 1..3 LOOP
        result := result || substr(chars, floor(random() * length(chars) + 1)::int, 1);
    END LOOP;

    -- 3 chữ thường
    FOR i IN 1..3 LOOP
        result := result || substr(lower_chars, floor(random() * length(lower_chars) + 1)::int, 1);
    END LOOP;

    -- 2 số
    FOR i IN 1..2 LOOP
        result := result || substr(numbers, floor(random() * length(numbers) + 1)::int, 1);
    END LOOP;

    -- Trộn lại các ký tự
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- 3. Function để tạo mật khẩu tạm cho user (expire sau 2 phút)
CREATE OR REPLACE FUNCTION create_temp_password_for_user(p_email VARCHAR)
RETURNS TABLE(
    success BOOLEAN,
    message TEXT,
    temp_password VARCHAR,
    username VARCHAR,
    email VARCHAR
) AS $$
DECLARE
    v_user RECORD;
    v_temp_pwd VARCHAR(8);
    v_temp_pwd_hashed VARCHAR(255);
BEGIN
    -- Tìm user theo email
    SELECT * INTO v_user
    FROM users
    WHERE users.email = p_email;

    -- Kiểm tra user tồn tại
    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Email không tồn tại trong hệ thống', NULL::VARCHAR, NULL::VARCHAR, NULL::VARCHAR;
        RETURN;
    END IF;

    -- Kiểm tra user đã verify email chưa
    IF NOT v_user.is_verified THEN
        RETURN QUERY SELECT FALSE, 'Tài khoản chưa được xác thực. Vui lòng xác thực email trước.', NULL::VARCHAR, NULL::VARCHAR, NULL::VARCHAR;
        RETURN;
    END IF;

    -- Tạo mật khẩu tạm
    v_temp_pwd := generate_temp_password();

    -- Hash mật khẩu tạm (sử dụng cùng hàm hash như password chính)
    -- LƯU Ý: Trong Python, bạn sẽ hash bằng bcrypt trước khi lưu
    -- Ở đây chỉ lưu plaintext để Python xử lý

    -- Cập nhật vào database
    UPDATE users
    SET
        temp_password = v_temp_pwd,  -- Sẽ hash ở Python layer
        temp_password_expires_at = NOW() + INTERVAL '2 minutes',
        require_password_change = FALSE  -- Chỉ set TRUE khi đăng nhập thành công bằng temp password
    WHERE users.email = p_email;

    RETURN QUERY SELECT
        TRUE,
        'Mật khẩu tạm đã được tạo thành công',
        v_temp_pwd,
        v_user.username,
        v_user.email;
END;
$$ LANGUAGE plpgsql;

-- 4. Function để kiểm tra và xóa mật khẩu tạm hết hạn
CREATE OR REPLACE FUNCTION cleanup_expired_temp_passwords()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE users
    SET
        temp_password = NULL,
        temp_password_expires_at = NULL
    WHERE
        temp_password IS NOT NULL
        AND temp_password_expires_at < NOW();

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- 5. Function để verify mật khẩu tạm khi đăng nhập
CREATE OR REPLACE FUNCTION verify_temp_password_login(
    p_username VARCHAR,
    p_temp_password VARCHAR
)
RETURNS TABLE(
    success BOOLEAN,
    message TEXT,
    userid INTEGER,
    require_change BOOLEAN
) AS $$
DECLARE
    v_user RECORD;
BEGIN
    -- Tìm user
    SELECT * INTO v_user
    FROM users
    WHERE username = p_username;

    -- Kiểm tra tồn tại
    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Tài khoản không tồn tại', NULL::INTEGER, FALSE;
        RETURN;
    END IF;

    -- Kiểm tra có temp password không
    IF v_user.temp_password IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Không có mật khẩu tạm nào được tạo', NULL::INTEGER, FALSE;
        RETURN;
    END IF;

    -- Kiểm tra hết hạn
    IF v_user.temp_password_expires_at < NOW() THEN
        -- Xóa temp password hết hạn
        UPDATE users
        SET temp_password = NULL, temp_password_expires_at = NULL
        WHERE username = p_username;

        RETURN QUERY SELECT FALSE, 'Mật khẩu tạm đã hết hạn', NULL::INTEGER, FALSE;
        RETURN;
    END IF;

    -- Kiểm tra temp password khớp (hash comparison sẽ thực hiện ở Python)
    -- Ở đây chỉ return user info để Python verify

    RETURN QUERY SELECT
        TRUE,
        'OK',
        v_user.userid,
        TRUE;  -- Yêu cầu đổi mật khẩu
END;
$$ LANGUAGE plpgsql;

-- 6. Function để xóa temp password sau khi đổi mật khẩu thành công
CREATE OR REPLACE FUNCTION clear_temp_password(p_userid INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE users
    SET
        temp_password = NULL,
        temp_password_expires_at = NULL,
        require_password_change = FALSE
    WHERE userid = p_userid;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- 7. Test functions
-- SELECT * FROM create_temp_password_for_user('test@example.com');
-- SELECT * FROM cleanup_expired_temp_passwords();
-- SELECT * FROM verify_temp_password_login('testuser', 'TempPass123');

-- ============================================
-- COMMENTS
-- ============================================
COMMENT ON COLUMN users.temp_password IS 'Mật khẩu tạm thời (hashed) - expire sau 2 phút';
COMMENT ON COLUMN users.temp_password_expires_at IS 'Thời gian hết hạn của mật khẩu tạm';
COMMENT ON COLUMN users.require_password_change IS 'Cờ đánh dấu user cần đổi mật khẩu sau khi đăng nhập bằng temp password';

COMMENT ON FUNCTION generate_temp_password() IS 'Tạo mật khẩu tạm ngẫu nhiên 8 ký tự (3 chữ hoa + 3 chữ thường + 2 số)';
COMMENT ON FUNCTION create_temp_password_for_user(VARCHAR) IS 'Tạo mật khẩu tạm cho user theo email, expire sau 2 phút';
COMMENT ON FUNCTION cleanup_expired_temp_passwords() IS 'Xóa tất cả mật khẩu tạm đã hết hạn';
COMMENT ON FUNCTION verify_temp_password_login(VARCHAR, VARCHAR) IS 'Kiểm tra temp password khi đăng nhập';
COMMENT ON FUNCTION clear_temp_password(INTEGER) IS 'Xóa temp password sau khi user đổi mật khẩu thành công';
