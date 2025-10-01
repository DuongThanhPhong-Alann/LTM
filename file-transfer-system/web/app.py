from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
import os
from supabase import create_client
import tempfile
import uuid
import re
from datetime import datetime
from services.storage_service import StorageService
from services.user_service import UserService
from flask import Response

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Thay đổi thành một key bí mật thực tế

# Cấu hình Supabase
SUPABASE_URL = "https://qrzycoatheltpfiztkeh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFyenljb2F0aGVsdHBmaXp0a2VoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODY3NjA1NiwiZXhwIjoyMDc0MjUyMDU2fQ.3JmRXRDs-QcEQDHNghjTJEPvoEHA3Zx5MpioHTh9rWM"

# Khởi tạo services
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
storage_service = StorageService(supabase_client)
user_service = UserService(supabase_client)

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Xác định tab đang được chọn (công khai/riêng tư)
    tab = request.args.get('tab', 'private')  # Mặc định hiển thị tab riêng tư
    
    # Lấy danh sách file với metadata
    files = storage_service.list_files(
        current_user=session['user'],
        public_only=(tab == 'public')
    )
    
    if files is None:
        # None -> network/connection error while talking to Supabase
        flash('Lỗi kết nối tới dịch vụ lưu trữ (Supabase). Vui lòng kiểm tra kết nối mạng hoặc cấu hình Supabase.', 'error')
        files = []
    elif not files:
        # Empty list is a valid state: no files in bucket
        files = []
    
    return render_template('index.html', 
                         files=files,
                         username=session['user'],
                         role=session.get('role', ''),
                         current_tab=tab)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not all([username, password, confirm_password]):
            flash('Vui lòng điền đầy đủ thông tin!', 'error')
            return redirect(url_for('register'))
            
        if password != confirm_password:
            flash('Mật khẩu không khớp!', 'error')
            return redirect(url_for('register'))
            
        success = user_service.register(username, password)
        if success:
            flash('Đăng ký tài khoản thành công!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Tên đăng nhập đã tồn tại hoặc có lỗi xảy ra!', 'error')
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        user = user_service.login(username, password)
        if user:
            session['user'] = username
            session['role'] = user.get('role', 'user')
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Sai tên đăng nhập hoặc mật khẩu!', 'error')
    
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

    # Đọc và kiểm tra file
    file_content = file.read()
    if len(file_content) == 0:
        flash('File rỗng!', 'error')
        return redirect(url_for('index'))
    
    # Lấy trạng thái công khai/riêng tư
    visibility = request.form.get('visibility', 'private')
    is_public = visibility == 'public'
        
    success = storage_service.upload_file(
        file_content,
        file.filename,
        file.content_type,
        session['user'],
        is_public
    )
    if isinstance(success, dict):
        if success.get('success'):
            flash(f'File {file.filename} đã được mã hóa và tải lên thành công!', 'success')
        else:
            flash(success.get('error', 'Lỗi khi tải lên file!'), 'error')
    else:
        # backward compatibility: truthy means success
        if success:
            flash(f'File {file.filename} đã được mã hóa và tải lên thành công!', 'success')
        else:
            flash('Lỗi khi tải lên file!', 'error')
        
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download(filename):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    result = storage_service.download_file(filename)
    if not result:
        flash('Lỗi khi tải xuống file!', 'error')
        return redirect(url_for('index'))

    # If storage_service returned a structured error (e.g., encrypted missing key)
    if isinstance(result, dict) and result.get('error') == 'encrypted_missing_key':
        flash('File được phát hiện đã được mã hóa nhưng khóa giải mã không có (metadata bị thiếu). Không thể tải xuống được.', 'error')
        return redirect(url_for('index'))

    file_data, original_filename, mime_type = result
    
    # Tạo temporary file để lưu file đã giải mã
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file_data)
        tmp.flush()
        
        # Gửi file cho client
        return send_file(
            tmp.name,
            as_attachment=True,
            download_name=original_filename,
            mimetype=mime_type or 'application/octet-stream'
        )

@app.route('/delete/<filename>')
def delete(filename):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') != 'admin':
        flash('Bạn không có quyền xóa file!', 'error')
        return redirect(url_for('index'))
        
    if storage_service.delete_file(filename):
        flash(f'File {filename} đã được xóa!', 'success')
    else:
        flash('Lỗi khi xóa file!', 'error')
        
    return redirect(url_for('index'))


@app.route('/preview/<filename>')
def preview(filename):
    if 'user' not in session:
        return redirect(url_for('login'))

    result = storage_service.download_file(filename)
    if not result:
        # Try fallback: public URL or signed URL
        public = storage_service.get_public_url(filename)
        if public:
            return redirect(public)
        signed = storage_service.create_signed_url(filename, expires=120)
        if signed:
            return redirect(signed)

        flash('Lỗi khi tải xuống file để xem trước!', 'error')
        return redirect(url_for('index'))

    file_data, original_filename, mime_type = result

    # Serve inline for images and PDFs
    if mime_type and (mime_type.startswith('image/') or mime_type == 'application/pdf'):
        return Response(file_data, mimetype=mime_type)

    # For other types, render a minimal HTML viewer embedding the file as base64 (fallback)
    try:
        import base64
        b64 = base64.b64encode(file_data).decode('ascii')
        html = f"""
        <!doctype html>
        <html>
        <head><meta charset='utf-8'><title>Preview - {original_filename}</title></head>
        <body>
          <h4>{original_filename}</h4>
          <p>Loại MIME: {mime_type}</p>
          <p>Nếu file không hiển thị, hãy <a href='{url_for('download', filename=filename)}'>tải về</a>.</p>
          <pre style='white-space: pre-wrap; word-break: break-word;'>
            <a href='data:{mime_type};base64,{b64}' download='{original_filename}'>Tải file</a>
          </pre>
        </body>
        </html>
        """
        return Response(html, mimetype='text/html')
    except Exception as e:
        flash('Không thể hiển thị xem trước cho file này.', 'error')
        return redirect(url_for('index'))


@app.route('/preview_stream/<path:filename>')
def preview_stream(filename):
    import base64  # Import base64 ở đây
    
    if 'user' not in session:
        return redirect(url_for('login'))

    result = storage_service.download_file(filename)
    if not result:
        # Try redirect to public/signed url as fallback
        public = storage_service.get_public_url(filename)
        if public:
            return redirect(public)
        signed = storage_service.create_signed_url(filename, expires=120)
        if signed:
            return redirect(signed)
        return Response('<h4>Không thể tải file để xem trước.</h4>', mimetype='text/html')

    if isinstance(result, dict) and result.get('error') == 'encrypted_missing_key':
        return Response('<h4>File này đã được mã hóa nhưng khóa giải mã không có. Vui lòng liên hệ quản trị.</h4>', mimetype='text/html')

    file_data, original_filename, mime_type = result

    # Ensure decrypted files are handled correctly
    if not file_data:
        return Response('<h4>Không thể tải file để xem trước.</h4>', mimetype='text/html')

    # Inline preview for images
    if mime_type and mime_type.startswith('image/'):
        return Response(file_data, mimetype=mime_type)

    # PDF preview using iframe with fallback
    if mime_type == 'application/pdf':
        try:
            pdf_base64 = base64.b64encode(file_data).decode('ascii')
            html = f"""
            <!doctype html>
            <html>
            <head>
                <meta charset='utf-8'>
                <title>Preview - {original_filename}</title>
                <style>
                    body {{ margin: 0; padding: 0; height: 100vh; }}
                    .container {{ height: 100%; }}
                    #pdf-viewer {{ width: 100%; height: 100%; border: none; }}
                    .fallback {{ 
                        text-align: center;
                        padding: 20px;
                        font-family: Arial, sans-serif;
                    }}
                    .download-btn {{ 
                        display: inline-block;
                        padding: 10px 20px;
                        background-color: #007bff;
                        color: white;
                        text-decoration: none;
                        border-radius: 5px;
                        margin-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <iframe id="pdf-viewer" 
                            src="data:application/pdf;base64,{pdf_base64}"
                            type="application/pdf">
                        <div class="fallback">
                            <p>Trình duyệt của bạn không hỗ trợ xem PDF trực tiếp.</p>
                            <a href='{url_for('download', filename=filename)}' class="download-btn">
                                Tải xuống PDF
                            </a>
                        </div>
                    </iframe>
                </div>
            </body>
            </html>
            """
            return Response(html, mimetype='text/html')
        except Exception as e:
            html = f"""
            <!doctype html>
            <html>
            <head>
                <meta charset='utf-8'>
                <title>Preview - {original_filename}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 20px; text-align: center; }}
                    .download-btn {{ 
                        display: inline-block;
                        padding: 10px 20px;
                        background-color: #007bff;
                        color: white;
                        text-decoration: none;
                        border-radius: 5px;
                        margin-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <h3>{original_filename}</h3>
                <p>Không thể hiển thị PDF trực tiếp.</p>
                <p>Vui lòng tải về để xem.</p>
                <a href='{url_for('download', filename=filename)}' class="download-btn">Tải xuống PDF</a>
            </body>
            </html>
            """
            return Response(html, mimetype='text/html')
        return Response(html, mimetype='text/html')

    # Handle .doc files with a more informative message
    if mime_type == 'application/msword' or mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        html = f"""
        <!doctype html>
        <html>
        <head>
            <meta charset='utf-8'>
            <title>Preview - {original_filename}</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .container {{ text-align: center; }}
                .download-btn {{ 
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 20px;
                }}
                .download-btn:hover {{ 
                    background-color: #0056b3; 
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h3>{original_filename}</h3>
                <p>Tệp Word không thể xem trước trực tiếp trên trình duyệt.</p>
                <p>Vui lòng tải về để xem nội dung.</p>
                <a href='{url_for('download', filename=filename)}' class="download-btn">Tải xuống</a>
            </div>
        </body>
        </html>
        """
        return Response(html, mimetype='text/html')

    # Display content for text files
    if mime_type and mime_type.startswith('text/'):
        text_content = file_data.decode('utf-8', errors='replace')
        html = f"""
        <!doctype html>
        <html>
        <head>
            <meta charset='utf-8'>
            <title>Preview - {original_filename}</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                pre {{ 
                    white-space: pre-wrap; 
                    word-wrap: break-word;
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 5px;
                }}
            </style>
        </head>
        <body>
            <h4>{original_filename}</h4>
            <pre>{text_content}</pre>
        </body>
        </html>
        """
        return Response(html, mimetype='text/html')

    # Fallback HTML viewer for other types
    import base64
    b64 = base64.b64encode(file_data).decode('ascii')
    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset='utf-8'>
        <title>Preview - {original_filename}</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; text-align: center; }}
            .download-btn {{ 
                display: inline-block;
                padding: 10px 20px;
                background-color: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 10px;
            }}
            .download-btn:hover {{ 
                background-color: #0056b3; 
            }}
        </style>
    </head>
    <body>
        <h4>{original_filename}</h4>
        <p>Loại tệp: {mime_type}</p>
        <p>Tệp này không thể xem trước trực tiếp.</p>
        <a href='{url_for('download', filename=filename)}' class="download-btn">Tải xuống</a>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not all([current_password, new_password, confirm_password]):
            flash('Vui lòng điền đầy đủ thông tin!', 'error')
            return redirect(url_for('profile'))
            
        if new_password != confirm_password:
            flash('Mật khẩu mới không khớp!', 'error')
            return redirect(url_for('profile'))
            
        if user_service.change_password(session['user'], current_password, new_password):
            flash('Mật khẩu đã được cập nhật thành công!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Mật khẩu hiện tại không đúng hoặc có lỗi xảy ra!', 'error')
            
    return render_template('profile.html', username=session['user'])

if __name__ == '__main__':
    # Chạy server trên port 5000 và cho phép truy cập từ mọi IP
    app.run(host='0.0.0.0', port=5000, debug=True)