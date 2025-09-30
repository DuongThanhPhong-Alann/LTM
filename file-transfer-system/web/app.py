from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
import os
from supabase import create_client
import tempfile
from datetime import datetime
import json
from base64 import b64encode, b64decode
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import json
from base64 import b64encode
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Thay đổi thành một key bí mật thực tế

# Cấu hình Supabase
SUPABASE_URL = "https://qrzycoatheltpfiztkeh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFyenljb2F0aGVsdHBmaXp0a2VoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODY3NjA1NiwiZXhwIjoyMDc0MjUyMDU2fQ.3JmRXRDs-QcEQDHNghjTJEPvoEHA3Zx5MpioHTh9rWM"
STORAGE_BUCKET = "files"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def derive_key(password, salt):
    """Tạo key từ password và salt sử dụng PBKDF2"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def encrypt_file(file_data, password):
    """Mã hóa file data với password"""
    # Tạo salt ngẫu nhiên
    salt = os.urandom(16)
    
    # Tạo key từ password và salt
    key = derive_key(password, salt)
    
    # Khởi tạo Fernet cipher với key
    cipher = Fernet(key)
    
    # Mã hóa data
    encrypted_data = cipher.encrypt(file_data)
    
    # Trả về salt và encrypted data
    return {
        'salt': b64encode(salt).decode('utf-8'),
        'encrypted_data': encrypted_data,
        'key': key.decode('utf-8')
    }

def decrypt_file(encrypted_data, key, salt):
    """Giải mã file với key và salt"""
    cipher = Fernet(key.encode())
    decrypted_data = cipher.decrypt(encrypted_data)
    return decrypted_data

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Lấy danh sách file
    try:
        files = supabase.storage.from_(STORAGE_BUCKET).list()
    except Exception as e:
        files = []
        flash(f'Lỗi khi lấy danh sách file: {str(e)}', 'error')
    
    return render_template('index.html', 
                         files=files, 
                         username=session['user'],
                         role=session.get('role', ''))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if not all([username, password, confirm_password]):
            flash('Vui lòng điền đầy đủ thông tin!', 'error')
            return redirect(url_for('register'))
            
        if password != confirm_password:
            flash('Mật khẩu không khớp!', 'error')
            return redirect(url_for('register'))
            
        try:
            # Kiểm tra username đã tồn tại chưa
            response = supabase.table("users").select("*").eq("username", username).execute()
            
            if response.data:
                flash('Tên đăng nhập đã tồn tại!', 'error')
                return redirect(url_for('register'))
                
            # Tạo user mới
            supabase.table("users").insert({
                "username": username,
                "password": password,
                "role": "user"  # Mặc định là user thường
            }).execute()
            
            flash('Đăng ký tài khoản thành công!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Lỗi khi đăng ký: {str(e)}', 'error')
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            # Xác thực qua bảng users
            response = supabase.table("users").select("*").eq("username", username).execute()
            
            if response.data:
                user_data = response.data[0]
                stored_password = user_data.get('password')
                
                if stored_password == password:
                    session['user'] = username
                    session['role'] = user_data.get('role')
                    flash('Đăng nhập thành công!', 'success')
                    return redirect(url_for('index'))
                
            flash('Sai tên đăng nhập hoặc mật khẩu!', 'error')
        except Exception as e:
            flash(f'Lỗi khi đăng nhập: {str(e)}', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Đã đăng xuất!', 'success')
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if 'file' not in request.files:
        flash('Không có file được chọn!', 'error')
        return redirect(url_for('index'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Không có file được chọn!', 'error')
        return redirect(url_for('index'))
        
    try:
        # Đọc nội dung file từ FileStorage object
        file_content = file.read()
        
        # Mã hóa file trước khi upload
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        f = Fernet(key)
        encrypted_content = f.encrypt(file_content)
        
        # Upload file đã mã hóa lên Supabase
        response = supabase.storage.from_(STORAGE_BUCKET).upload(
            path=file.filename,
            file=encrypted_content,
            file_options={
                "content-type": file.content_type,
                "metadata": {
                    "encrypted": "true",
                    "encryption_key": key.decode(),
                    "original_size": len(file_content),
                    "uploaded_by": session['user'],
                    "uploaded_at": datetime.now().isoformat()
                }
            }
        )
        
        flash(f'File {file.filename} đã được mã hóa và tải lên thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi khi upload file: {str(e)}', 'error')
        
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download(filename):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    try:
        # Lấy thông tin file từ Supabase
        file_info = supabase.storage.from_(STORAGE_BUCKET).list()
        file_meta = None
        for file in file_info:
            if file['name'] == filename:
                file_meta = file.get('metadata', {})
                break
                
        # Download file từ Supabase
        encrypted_data = supabase.storage.from_(STORAGE_BUCKET).download(filename)
        
        # Kiểm tra xem file có được mã hóa không
        if file_meta and file_meta.get('encrypted') == 'true':
            # Lấy key và giải mã
            from cryptography.fernet import Fernet
            encryption_key = file_meta.get('encryption_key')
            if encryption_key:
                f = Fernet(encryption_key.encode())
                decrypted_data = f.decrypt(encrypted_data)
            else:
                flash('Không tìm thấy key để giải mã file!', 'error')
                return redirect(url_for('index'))
        else:
            decrypted_data = encrypted_data

        # Tạo temporary file để lưu file đã giải mã
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # Ghi vào temporary file
            tmp.write(decrypted_data)
            tmp.flush()
            
            # Gửi file cho client
            return send_file(
                tmp.name,
                as_attachment=True,
                download_name=filename,
                mimetype='application/octet-stream'
            )
    except Exception as e:
        flash(f'Lỗi khi download file: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/delete/<filename>')
def delete(filename):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') != 'admin':
        flash('Bạn không có quyền xóa file!', 'error')
        return redirect(url_for('index'))
        
    try:
        # Xóa file từ Supabase
        supabase.storage.from_(STORAGE_BUCKET).remove([filename])
        flash(f'File {filename} đã được xóa!', 'success')
    except Exception as e:
        flash(f'Lỗi khi xóa file: {str(e)}', 'error')
        
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([current_password, new_password, confirm_password]):
            flash('Vui lòng điền đầy đủ thông tin!', 'error')
            return redirect(url_for('profile'))
            
        if new_password != confirm_password:
            flash('Mật khẩu mới không khớp!', 'error')
            return redirect(url_for('profile'))
        
        try:
            # Kiểm tra mật khẩu hiện tại
            response = supabase.table("users").select("*").eq("username", session['user']).execute()
            
            if response.data and response.data[0]['password'] == current_password:
                # Cập nhật mật khẩu mới
                supabase.table("users").update({"password": new_password}).eq("username", session['user']).execute()
                flash('Mật khẩu đã được cập nhật thành công!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Mật khẩu hiện tại không đúng!', 'error')
        except Exception as e:
            flash(f'Lỗi khi cập nhật mật khẩu: {str(e)}', 'error')
            
    return render_template('profile.html', username=session['user'])

if __name__ == '__main__':
    # Chạy server trên port 5000 và cho phép truy cập từ mọi IP
    app.run(host='0.0.0.0', port=5000, debug=True)