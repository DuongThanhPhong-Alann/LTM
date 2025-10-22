from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, Response, jsonify
import os
import time
from supabase import create_client
import tempfile
import uuid
import re
from datetime import datetime
import pytz
import win32com
from services.storage_service import StorageService
from services.user_service import UserService
import base64
import mimetypes
from docx import Document
import subprocess
import re
import random
import requests
from datetime import datetime, timedelta

def convert_docx_to_doc(docx_path):
    try:
        # Initialize COM in the current thread
        pythoncom.CoInitialize() # type: ignore
        
        # Create a temporary file for the .doc version
        temp_dir = tempfile.mkdtemp()
        doc_path = os.path.join(temp_dir, 'converted.doc')
        
        # Create Word application object
        word = win32com.client.Dispatch('Word.Application')
        word.Visible = False
        
        try:
            # Open the docx file
            doc = word.Documents.Open(docx_path)
            
            # Save as .doc format (Word 97-2003)
            doc.SaveAs2(doc_path, FileFormat=0)  # 0 = Word 97-2003 format
            
            # Close the document
            doc.Close()
            
            # Read the converted file
            with open(doc_path, 'rb') as f:
                doc_content = f.read()
            
            return doc_content
            
        finally:
            # Clean up
            word.Quit()
            
            # Try to remove temporary files
            try:
                if os.path.exists(doc_path):
                    os.remove(doc_path)
                os.rmdir(temp_dir)
            except:
                pass
            
            # Uninitialize COM
            pythoncom.CoUninitialize() # type: ignore
            
    except Exception as e:
        print(f"Error converting docx to doc: {str(e)}")
        return None

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
# Ensure session cookie settings are explicit for local development
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

# Helper function to get Vietnam time
def get_vietnam_time():
    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    return datetime.now(vietnam_tz).isoformat()

# Helper function for retry logic
def retry_supabase_operation(operation, max_retries=3):
    """Retry Supabase operations with exponential backoff"""
    import time
    import socket
    
    for attempt in range(max_retries):
        try:
            return operation()
        except (socket.error, ConnectionError, OSError) as e:
            if attempt == max_retries - 1:
                print(f"Final retry failed: {str(e)}")
                # Return empty result instead of raising error
                return type('MockResult', (), {'data': []})()
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"Retry attempt {attempt + 1} after {wait_time}s: {str(e)}")
            time.sleep(wait_time)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"Retry attempt {attempt + 1} after {wait_time}s: {str(e)}")
            time.sleep(wait_time)


def execute_with_retries(operation, max_retries=5, base_delay=0.2):
    """Retry wrapper that specifically handles transient WinError 10035 and similar socket issues."""
    import time as _time
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return operation()
        except Exception as e:
            last_exc = e
            err_str = str(e)
            # Check for Windows non-blocking socket transient error
            if '10035' in err_str or 'non-blocking socket' in err_str.lower() or isinstance(e, OSError):
                wait = base_delay * (2 ** (attempt - 1))
                print(f"[RETRY] Transient socket error detected (attempt {attempt}/{max_retries}): {err_str}. Waiting {wait}s and retrying...")
                _time.sleep(wait)
                continue
            # For other exceptions, re-raise immediately on last attempt or rethrow
            print(f"[ERROR] Non-transient error in execute_with_retries: {err_str}")
            raise
    # After retries, return a MockResult similar to retry_supabase_operation
    print(f"[ERROR] execute_with_retries exhausted retries. Last error: {last_exc}")
    return type('MockResult', (), {'data': []})()

# Register custom MIME types for uncommon file extensions
mimetypes.add_type('application/octet-stream', '.docthif')
mimetypes.add_type('application/octet-stream', '.custom')
mimetypes.add_type('application/octet-stream', '.unknown')
mimetypes.add_type('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx')
mimetypes.add_type('application/msword', '.doc')
mimetypes.add_type('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx')
mimetypes.add_type('application/vnd.ms-excel', '.xls')
mimetypes.add_type('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx')
mimetypes.add_type('application/vnd.ms-powerpoint', '.ppt')
mimetypes.add_type('application/vnd.oasis.opendocument.text', '.odt')
mimetypes.add_type('application/vnd.oasis.opendocument.spreadsheet', '.ods')
mimetypes.add_type('application/vnd.oasis.opendocument.presentation', '.odp')
mimetypes.add_type('application/x-rar-compressed', '.rar')
mimetypes.add_type('application/zip', '.zip')
mimetypes.add_type('application/x-7z-compressed', '.7z')
mimetypes.add_type('application/octet-stream', '.*')

# Cấu hình Supabase
SUPABASE_URL = "https://qrzycoatheltpfiztkeh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFyenljb2F0aGVsdHBmaXp0a2VoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODY3NjA1NiwiZXhwIjoyMDc0MjUyMDU2fQ.3JmRXRDs-QcEQDHNghjTJEPvoEHA3Zx5MpioHTh9rWM"

# Tạo Supabase client với timeout
from supabase import create_client, Client
import httpx

# Cấu hình httpx timeout global
httpx._config.DEFAULT_TIMEOUT = httpx.Timeout(30.0)

# Cấu hình Supabase client
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
storage_service = StorageService(supabase_client)
user_service = UserService(supabase_client)

# ==================== AUTH ROUTES ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        # Sử dụng login_with_temp_password để hỗ trợ cả mật khẩu tạm
        success, user, requires_change, message = user_service.login_with_temp_password(username, password)

        if success and user:
            session['user'] = username
            session['role'] = user.get('role', 'user')
            session['userid'] = user.get('userid')

            # Nếu đăng nhập bằng temp password, lưu flag để redirect đến trang đổi mật khẩu
            if requires_change:
                session['require_password_change'] = True
                flash(message, 'warning')
                return redirect(url_for('force_change_password_page'))

            flash('Đăng nhập thành công!', 'success')
            # Debug info to help troubleshoot session persistence issues
            try:
                print(f"[DEBUG] login success: username={username}, session_keys={list(session.keys())}")
            except Exception as _:
                print("[DEBUG] login success (could not read session keys)")

            # Redirect về trang gốc nếu có, không thì về index
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash(message if message else 'Sai tên đăng nhập hoặc mật khẩu!', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Đăng xuất và set offline"""
    if 'user' in session:
        user = user_service.get_user_profile(session['user'])
        if user:
            user_service.set_offline(user['userid'])

    session.clear()
    flash('Đã đăng xuất!', 'success')
    return redirect(url_for('login'))

# ==================== FORGOT PASSWORD ROUTES ====================

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    """API endpoint để tạo mật khẩu tạm và gửi email"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()

        if not email:
            return jsonify({"success": False, "message": "Email không được để trống"}), 400

        # Validate email format
        if not user_service.validate_email(email):
            return jsonify({"success": False, "message": "Email không hợp lệ"}), 400

        # Tạo mật khẩu tạm
        success, temp_password, username, message = user_service.create_temp_password(email)

        if not success:
            return jsonify({"success": False, "message": message}), 400

        # Gửi email qua n8n webhook
        payload = {
            "email": email,
            "username": username,
            "temp_password": temp_password,
            "timestamp": datetime.now().isoformat(),
            "login_url": request.host_url + "login",
            "expires_in_minutes": 2
        }

        try:
            response = requests.post(
                N8N_FORGOT_PASSWORD_WEBHOOK_URL,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                print(f"✅ Forgot password email sent successfully to {email}")
                return jsonify({
                    "success": True,
                    "message": f"Mật khẩu tạm đã được gửi đến {email}. Vui lòng kiểm tra email của bạn."
                }), 200
            else:
                print(f"⚠️ n8n webhook returned status {response.status_code}")
                # Fallback: in ra console để dev có thể test
                print(f"\n{'='*60}")
                print(f"🔐 TEMP PASSWORD (n8n failed - fallback)")
                print(f"{'='*60}")
                print(f"Email: {email}")
                print(f"Username: {username}")
                print(f"Temp Password: {temp_password}")
                print(f"Expires in: 2 minutes")
                print(f"{'='*60}\n")
                return jsonify({
                    "success": True,
                    "message": f"⚠️ Email service có lỗi. Mật khẩu tạm: {temp_password}"
                }), 200

        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending forgot password email via n8n: {str(e)}")
            # Fallback: in ra console để dev có thể test
            print(f"\n{'='*60}")
            print(f"🔐 TEMP PASSWORD (n8n offline - fallback)")
            print(f"{'='*60}")
            print(f"Email: {email}")
            print(f"Username: {username}")
            print(f"Temp Password: {temp_password}")
            print(f"Expires in: 2 minutes")
            print(f"Login URL: {request.host_url}login")
            print(f"{'='*60}\n")
            return jsonify({
                "success": True,
                "message": f"⚠️ Email service offline. Mật khẩu tạm: {temp_password} (Kiểm tra console)"
            }), 200

    except Exception as e:
        print(f"Error in forgot_password: {str(e)}")
        return jsonify({"success": False, "message": "Có lỗi xảy ra. Vui lòng thử lại."}), 500

@app.route('/change-password-required', methods=['GET', 'POST'])
def force_change_password_page():
    """Trang bắt buộc đổi mật khẩu sau khi đăng nhập bằng temp password"""
    # Kiểm tra user đã đăng nhập chưa
    if 'user' not in session:
        return redirect(url_for('login'))

    # Kiểm tra có require password change không
    if not session.get('require_password_change', False):
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validate
        if not new_password or not confirm_password:
            flash('Vui lòng nhập đầy đủ thông tin!', 'error')
            return render_template('force_change_password.html')

        if new_password != confirm_password:
            flash('Mật khẩu xác nhận không khớp!', 'error')
            return render_template('force_change_password.html')

        # Validate password strength
        is_valid, msg = user_service.validate_password(new_password)
        if not is_valid:
            flash(msg, 'error')
            return render_template('force_change_password.html')

        # Đổi mật khẩu
        userid = session.get('userid')
        success, message = user_service.force_change_password(userid, new_password)

        if success:
            # Xóa flag require_password_change
            session.pop('require_password_change', None)
            flash('Đổi mật khẩu thành công! Bạn có thể sử dụng mật khẩu mới để đăng nhập lần sau.', 'success')
            return redirect(url_for('index'))
        else:
            flash(message, 'error')
            return render_template('force_change_password.html')

    return render_template('force_change_password.html')

# ==================== FILE ROUTES ====================

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    tab = request.args.get('tab', 'private')
    
    files = storage_service.list_files(
        current_user=session['user'],
        public_only=(tab == 'public')
    )
    
    if files is None:
        flash('Lỗi kết nối tới dịch vụ lưu trữ (Supabase). Vui lòng kiểm tra kết nối mạng hoặc cấu hình Supabase.', 'error')
        files = []
    elif not files:
        files = []
    
    return render_template('index.html', 
                         files=files,
                         username=session['user'],
                         role=session.get('role', ''),
                         current_tab=tab)

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    files = request.files.getlist('file')
    if not files:
        flash('Không có file được chọn!', 'error')
        return redirect_back('index')

    upload_results = []
    for file in files:
        if not file or file.filename == '':
            upload_results.append((None, False, 'No filename'))
            continue

        file_content = file.read()
        if len(file_content) == 0:
            upload_results.append((file.filename, False, 'Empty file'))
            continue

        # Get file size
        file_size_bytes = len(file_content)
        if file_size_bytes < 1024:
            file_size_display = f"{file_size_bytes} bytes"
        elif file_size_bytes < 1024 * 1024:
            file_size_display = f"{file_size_bytes / 1024:.2f} KB"
        else:
            file_size_display = f"{file_size_bytes / (1024 * 1024):.2f} MB"

        # Improved MIME type detection
        content_type = file.content_type
        if not content_type or content_type == 'application/octet-stream':
            # Try to detect MIME type from file extension
            guessed_type, _ = mimetypes.guess_type(file.filename)
            if guessed_type:
                content_type = guessed_type
            else:
                # For unknown extensions, use generic binary type
                content_type = 'application/octet-stream'

        visibility = request.form.get('visibility', 'private')
        is_public = visibility == 'public'

        success = storage_service.upload_file(
            file_content,
            file.filename,
            content_type,
            session['user'],
            is_public
        )

        # Determine success for this file and optionally send email
        try:
            if isinstance(success, dict):
                ok = bool(success.get('success'))
            else:
                ok = bool(success)

            if ok:
                upload_results.append((file.filename, True, 'Uploaded'))
                try:
                    user_res = supabase_client.table('users').select('email').eq('username', session['user']).execute()
                    if user_res.data:
                        user_email = user_res.data[0].get('email')
                        send_file_uploaded_email(
                            email=user_email,
                            username=session['user'],
                            filename=file.filename,
                            filesize=file_size_display,
                            filetype=content_type,
                            visibility=visibility
                        )
                except Exception as e:
                    print(f"❌ Upload email error: {str(e)}")
            else:
                reason = success.get('error') if isinstance(success, dict) else 'Upload failed'
                upload_results.append((file.filename, False, reason))
        except Exception as e:
            upload_results.append((file.filename, False, str(e)))

    # Summarize upload results
    success_files = [name for name, ok, _ in upload_results if ok]
    failed = [(name, msg) for name, ok, msg in upload_results if not ok]

    if success_files:
        flash(f"Đã tải lên thành công: {', '.join(success_files)}", 'success')
    if failed:
        msgs = '; '.join([f"{n}: {m}" for n, m in failed])
        flash(f"Một số file không tải lên được: {msgs}", 'error')

    return redirect_back('index')

@app.route('/download/<filename>')
def download(filename):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Kiểm tra quyền truy cập file
    try:
        # Lấy thông tin file từ metadata
        metadata_resp = supabase_client.table('files_metadata').select('metadata').eq('filename', filename).execute()
        if not metadata_resp.data:
            return jsonify({'error': 'File không tồn tại.'}), 404
        
        metadata = metadata_resp.data[0].get('metadata', {})
        file_owner = metadata.get('uploaded_by')
        is_public = metadata.get('is_public', False)
        
        # Nếu file là public, cho phép download
        if is_public:
            pass  # Cho phép download
        # Nếu user là chủ sở hữu file, cho phép download
        elif file_owner == session['user']:
            pass  # Cho phép download
        # Nếu file được chia sẻ trong chat với user này
        else:
            has_access = False
            
            # Kiểm tra trong private messages
            private_msgs = supabase_client.table('privatemessages').select('*').contains('file_attachment', {'filename': filename}).execute()
            if private_msgs.data:
                for msg in private_msgs.data:
                    if msg['senderid'] == get_user_id(session['user']) or msg['receiverid'] == get_user_id(session['user']):
                        has_access = True
                        break
            
            # Kiểm tra trong group messages
            if not has_access:
                group_msgs = supabase_client.table('chatroommessages').select('*').contains('file_attachment', {'filename': filename}).execute()
                if group_msgs.data:
                    for msg in group_msgs.data:
                        member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', msg['roomid']).eq('userid', get_user_id(session['user'])).execute()
                        if member_check.data:
                            has_access = True
                            break
            
            if not has_access:
                return jsonify({'error': 'Bạn không có quyền truy cập file này.'}), 403
        
    except Exception as e:
        return jsonify({'error': f'Lỗi kiểm tra quyền truy cập: {str(e)}'}), 500
        
    try:
        result = storage_service.download_file(filename)
        if not result:
            return jsonify({'error': 'Không thể tải xuống file. File có thể không tồn tại hoặc đã bị xóa.'}), 404

        if isinstance(result, dict) and result.get('error') == 'encrypted_missing_key':
            return jsonify({'error': 'File được phát hiện đã được mã hóa nhưng khóa giải mã không có (metadata bị thiếu). Không thể tải xuống được.'}), 400

        file_data, original_filename, mime_type = result
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file_data)
            tmp.flush()
            
            return send_file(
                tmp.name,
                as_attachment=True,
                download_name=original_filename,
                mimetype=mime_type or 'application/octet-stream'
            )
    except Exception as e:
        return jsonify({'error': f'Lỗi khi tải xuống file: {str(e)}'}), 500

@app.route('/delete/<filename>')
def delete(filename):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Check if user is admin or file owner
    is_admin = session.get('role') == 'admin'
    is_owner = False
    file_owner_username = None
    file_owner_email = None
    original_filename = filename
    
    # Get file info to check ownership and get owner email
    files = storage_service.list_files(
        current_user=session['user'],
        public_only=False
    )
    
    for file in files:
        if file['name'] == filename:
            metadata = file.get('metadata', {})
            file_owner_username = metadata.get('uploaded_by')
            original_filename = metadata.get('original_filename', filename)
            
            if file_owner_username == session['user']:
                is_owner = True
            break
    
    if not is_admin and not is_owner:
        flash('Bạn không có quyền xóa file này!', 'error')
        return redirect_back('index')
    
    # Get file owner's email if we have the username
    if file_owner_username:
        try:
            owner_res = supabase_client.table('users').select('email, username').eq('username', file_owner_username).execute()
            if owner_res.data:
                file_owner_email = owner_res.data[0].get('email')
        except Exception as e:
            print(f"Error getting owner email: {str(e)}")
    
    # Delete the file
    if storage_service.delete_file(filename):
        flash(f'File {filename} đã được xóa!', 'success')
        
        # Send email notification to file owner
        if file_owner_email and file_owner_username:
            try:
                deleted_by = session['user']
                success, message = send_file_deleted_email(
                    email=file_owner_email,
                    username=file_owner_username,
                    filename=original_filename,
                    deleted_by=deleted_by
                )
                
                if not success:
                    print(f"Warning: Failed to send deletion notification email: {message}")
            except Exception as e:
                print(f"Warning: Exception when sending deletion email: {str(e)}")
    else:
        flash('Lỗi khi xóa file!', 'error')
        
    return redirect_back('index')


@app.route('/delete_files', methods=['POST'])
def delete_files():
    """Bulk delete multiple files. Expects form field 'filenames' as repeated values or JSON body with {filenames: []}."""
    if 'user' not in session:
        return redirect(url_for('login'))

    # Accept JSON or form
    data = None
    try:
        data = request.get_json(silent=True)
    except Exception:
        data = None

    if data and isinstance(data, dict):
        filenames = data.get('filenames') or []
    else:
        filenames = request.form.getlist('filenames') or []

    if not filenames:
        flash('Không có file nào được chọn để xóa!', 'error')
        return redirect_back('index')

    success_list = []
    failed_list = []

    # Pre-fetch all files for ownership checks
    try:
        all_files = storage_service.list_files(current_user=session['user'], public_only=False) or []
    except Exception as e:
        all_files = []

    for filename in filenames:
        # Find file metadata
        file_meta = None
        for f in all_files:
            if f['name'] == filename:
                file_meta = f
                break

        is_admin = session.get('role') == 'admin'
        is_owner = False
        file_owner_username = None
        original_filename = filename

        if file_meta:
            metadata = file_meta.get('metadata', {})
            file_owner_username = metadata.get('uploaded_by')
            original_filename = metadata.get('original_filename', filename)
            if file_owner_username == session['user']:
                is_owner = True

        if not is_admin and not is_owner:
            failed_list.append((filename, 'Không có quyền xóa'))
            continue

        # Attempt delete
        try:
            ok = storage_service.delete_file(filename)
            if ok:
                success_list.append(original_filename)
                # Notify owner if available
                if file_owner_username:
                    try:
                        owner_res = supabase_client.table('users').select('email').eq('username', file_owner_username).execute()
                        if owner_res.data:
                            owner_email = owner_res.data[0].get('email')
                            send_file_deleted_email(
                                email=owner_email,
                                username=file_owner_username,
                                filename=original_filename,
                                deleted_by=session['user']
                            )
                    except Exception:
                        pass
            else:
                failed_list.append((filename, 'Xóa thất bại'))
        except Exception as e:
            failed_list.append((filename, str(e)))

    if success_list:
        flash(f'Đã xóa thành công: {", ".join(success_list)}', 'success')
    if failed_list:
        msgs = '; '.join([f"{n}: {m}" for n, m in failed_list])
        flash(f'Một số file không xóa được: {msgs}', 'error')

    return redirect_back('index')

@app.route('/preview/<filename>')
def preview(filename):
    if 'user' not in session:
        return redirect(url_for('login'))

    # Kiểm tra quyền truy cập file (sử dụng logic tương tự như download)
    try:
        metadata_resp = supabase_client.table('files_metadata').select('metadata').eq('filename', filename).execute()
        if not metadata_resp.data:
            flash('File không tồn tại.', 'error')
            return redirect_back('index')

        metadata = metadata_resp.data[0].get('metadata', {})
        file_owner = metadata.get('uploaded_by')
        is_public = metadata.get('is_public', False)

        if not is_public and file_owner != session['user']:
            # Kiểm tra quyền truy cập trong chat
            has_access = False

            private_msgs = supabase_client.table('privatemessages').select('*').contains('file_attachment', {'filename': filename}).execute()
            if private_msgs.data:
                for msg in private_msgs.data:
                    if msg['senderid'] == get_user_id(session['user']) or msg['receiverid'] == get_user_id(session['user']):
                        has_access = True
                        break

            if not has_access:
                group_msgs = supabase_client.table('chatroommessages').select('*').contains('file_attachment', {'filename': filename}).execute()
                if group_msgs.data:
                    for msg in group_msgs.data:
                        member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', msg['roomid']).eq('userid', get_user_id(session['user'])).execute()
                        if member_check.data:
                            has_access = True
                            break

            if not has_access:
                flash('Bạn không có quyền xem file này.', 'error')
                return redirect_back('index')

    except Exception as e:
        flash(f'Lỗi kiểm tra quyền truy cập: {str(e)}', 'error')
        return redirect_back('index')

    result = storage_service.download_file(filename)
    if not result:
        flash('Lỗi khi tải xuống file để xem trước!', 'error')
        return redirect_back('index')

    file_data, original_filename, mime_type = result

    if mime_type and (mime_type.startswith('image/') or mime_type == 'application/pdf'):
        return Response(file_data, mimetype=mime_type)

    try:
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
        return redirect_back('index')

@app.route('/preview_stream/<path:filename>')
def preview_stream(filename):
    if 'user' not in session:
        return redirect(url_for('login'))

    # Kiểm tra quyền truy cập file
    try:
        metadata_resp = supabase_client.table('files_metadata').select('metadata').eq('filename', filename).execute()
        if not metadata_resp.data:
            return Response('<h4>File không tồn tại.</h4>', mimetype='text/html')
        
        metadata = metadata_resp.data[0].get('metadata', {})
        file_owner = metadata.get('uploaded_by')
        is_public = metadata.get('is_public', False)
        
        if not is_public and file_owner != session['user']:
            # Kiểm tra quyền truy cập trong chat
            has_access = False
            
            private_msgs = supabase_client.table('privatemessages').select('*').contains('file_attachment', {'filename': filename}).execute()
            if private_msgs.data:
                for msg in private_msgs.data:
                    if msg['senderid'] == get_user_id(session['user']) or msg['receiverid'] == get_user_id(session['user']):
                        has_access = True
                        break
            
            if not has_access:
                group_msgs = supabase_client.table('chatroommessages').select('*').contains('file_attachment', {'filename': filename}).execute()
                if group_msgs.data:
                    for msg in group_msgs.data:
                        member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', msg['roomid']).eq('userid', get_user_id(session['user'])).execute()
                        if member_check.data:
                            has_access = True
                            break
            
            if not has_access:
                return Response('<h4>Bạn không có quyền xem file này.</h4>', mimetype='text/html')
        
    except Exception as e:
        return Response(f'<h4>Lỗi kiểm tra quyền truy cập: {str(e)}</h4>', mimetype='text/html')

    result = storage_service.download_file(filename)
    if not result:
        return Response('<h4>Không thể tải file để xem trước.</h4>', mimetype='text/html')

    if isinstance(result, dict) and result.get('error') == 'encrypted_missing_key':
        return Response('<h4>File này đã được mã hóa nhưng khóa giải mã không có. Vui lòng liên hệ quản trị.</h4>', mimetype='text/html')

    file_data, original_filename, mime_type = result

    if not file_data:
        return Response('<h4>Không thể tải file để xem trước.</h4>', mimetype='text/html')

    if mime_type and mime_type.startswith('image/'):
        return Response(file_data, mimetype=mime_type)

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

# ==================== PROFILE ROUTES ====================

@app.route('/view_profile/<username>')
def view_profile(username):
    """Xem profile của user"""
    if 'user' not in session:
        return redirect(url_for('login'))
    
    profile_user = user_service.get_user_profile(username)
    if not profile_user:
        flash('Không tìm thấy người dùng!', 'error')
        return redirect(url_for('chat'))
    
    is_own_profile = (session['user'] == username)
    
    return render_template('view_profile.html', 
                         profile_user=profile_user,
                         is_own_profile=is_own_profile)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    """Chỉnh sửa thông tin cá nhân"""
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = user_service.get_user_profile(session['user'])
    if not user:
        flash('Không tìm thấy thông tin người dùng!', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        bio = request.form.get('bio', '').strip()
        phone = request.form.get('phone', '').strip()
        
        update_data = {
            'bio': bio if bio else None,
            'phone': phone if phone else None
        }
        
        if user_service.update_profile(user['userid'], update_data):
            flash('Đã cập nhật thông tin thành công!', 'success')
            return redirect(url_for('view_profile', username=session['user']))
        else:
            flash('Có lỗi khi cập nhật thông tin!', 'error')
    
    return render_template('edit_profile.html', user=user)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """Change password page"""
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
            return redirect_back('index')
        else:
            flash('Mật khẩu hiện tại không đúng hoặc có lỗi xảy ra!', 'error')

    return render_template('profile.html', username=session['user'])

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    """Upload ảnh đại diện"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    if 'avatar' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    
    if file_ext not in allowed_extensions:
        return jsonify({"error": "Invalid file type. Only PNG, JPG, JPEG, and GIF are allowed."}), 400
    
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 5 * 1024 * 1024:
        return jsonify({"error": "File too large. Maximum size is 5MB."}), 400
    
    user = user_service.get_user_profile(session['user'])
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    file_data = file.read()
    avatar_url = user_service.upload_avatar(user['userid'], file_data, file.filename)
    
    if avatar_url:
        return jsonify({"success": True, "avatar_url": avatar_url}), 200
    else:
        return jsonify({"error": "Failed to upload avatar"}), 500

# ==================== ACTIVITY TRACKING ====================

@app.route('/update_activity', methods=['POST'])
def update_activity():
    """Cập nhật hoạt động của user"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    user = user_service.get_user_profile(session['user'])
    if user:
        user_service.update_last_seen(user['userid'])
        return jsonify({"success": True}), 200
    
    return jsonify({"error": "User not found"}), 404

@app.route('/set_offline', methods=['POST'])
def set_offline():
    """Đặt trạng thái offline"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    user = user_service.get_user_profile(session['user'])
    if user:
        user_service.set_offline(user['userid'])
        return jsonify({"success": True}), 200
    
    return jsonify({"error": "User not found"}), 404

@app.route('/online_users')
def online_users():
    """Lấy danh sách users đang online"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    users = user_service.get_online_users()
    return jsonify({"users": users}), 200

# ==================== CHAT ROUTES ====================

@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect(url_for('login', next=request.url))
    rooms = []
    recent_chats = []

    my_res = supabase_client.table('users').select('userid, avatar_url').eq('username', session['user']).execute()
    my_id = my_res.data[0]['userid'] if my_res.data else None
    current_user_avatar = my_res.data[0].get('avatar_url') if my_res.data else None

    if my_id:
        members_res = supabase_client.table('chatroommembers').select('roomid').eq('userid', my_id).execute()
        room_ids = [member['roomid'] for member in (members_res.data or [])]
        
        if room_ids:
            rooms_res = supabase_client.table('chatrooms').select('*').in_('roomid', room_ids).execute()
            rooms = rooms_res.data if rooms_res.data else []
        
        sent_msgs = supabase_client.table('privatemessages').select('receiverid, content, createdat').eq('senderid', my_id).order('createdat', desc=True).execute()
        received_msgs = supabase_client.table('privatemessages').select('senderid, content, createdat').eq('receiverid', my_id).order('createdat', desc=True).execute()
        
        user_messages = {}
        
        if sent_msgs.data:
            for msg in sent_msgs.data:
                uid = msg['receiverid']
                if uid not in user_messages:
                    user_messages[uid] = {
                        'last_message': msg.get('content', ''),
                        'last_time': msg.get('createdat', '')
                    }
        
        if received_msgs.data:
            for msg in received_msgs.data:
                uid = msg['senderid']
                if uid not in user_messages:
                    user_messages[uid] = {
                        'last_message': msg.get('content', ''),
                        'last_time': msg.get('createdat', '')
                    }
                elif msg.get('createdat', '') > user_messages[uid]['last_time']:
                    user_messages[uid]['last_message'] = msg.get('content', '')
                    user_messages[uid]['last_time'] = msg.get('createdat', '')
        
        if user_messages:
            user_ids = list(user_messages.keys())
            users_res = supabase_client.table('users').select('userid, username, avatar_url, is_online').in_('userid', user_ids).execute()
            if users_res.data:
                recent_chats = [{
                    'userid': user['userid'],
                    'username': user['username'],
                    'avatar_url': user.get('avatar_url'),
                    'is_online': user.get('is_online', False),
                    'last_message': user_messages[user['userid']]['last_message']
                } for user in users_res.data]

    return render_template('chat.html', rooms=rooms, recent_chats=recent_chats, current_user_avatar=current_user_avatar)

@app.route('/create_room_page')
def create_room_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    users_res = supabase_client.table('users').select('userid,username').neq('username', session['user']).execute()
    private_users = users_res.data if users_res.data else []
    return render_template('create_room.html', private_users=private_users)

@app.route('/create_room', methods=['POST'])
def create_room():
    if 'user' not in session:
        return redirect(url_for('login'))
    room_name = request.form.get('room_name', '').strip()
    member_ids = request.form.getlist('members')
    if not room_name:
        flash('Tên phòng không được để trống!', 'error')
        return redirect(url_for('create_room_page'))
        
    exists = supabase_client.table('chatrooms').select('*').eq('roomname', room_name).execute()
    if exists.data:
        flash('Tên phòng đã tồn tại! Vui lòng chọn tên khác.', 'error')
        return redirect(url_for('create_room_page'))

    # Lấy userid của người tạo
    creator = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    if not creator.data:
        flash('Không tìm thấy thông tin người dùng!', 'error')
        return redirect(url_for('create_room_page'))

    creator_id = creator.data[0]['userid']

    try:
        # Tạo room với createdby
        res = supabase_client.table('chatrooms').insert({
            'roomname': room_name,
            'createdby': creator_id
        }).execute()
        if not res.data:
            flash('Tạo phòng thất bại!', 'error')
            return redirect(url_for('create_room_page'))
    except Exception as e:
        flash('Có lỗi xảy ra khi tạo phòng: ' + str(e), 'error')
        return redirect(url_for('create_room_page'))

    room_id = res.data[0]['roomid']

    # Thêm creator vào members (người tạo tự động là thành viên)
    supabase_client.table('chatroommembers').insert({
        'roomid': room_id,
        'userid': creator_id
    }).execute()

    # Thêm các members được chọn
    for uid in member_ids:
        if int(uid) != creator_id:  # Tránh duplicate creator
            supabase_client.table('chatroommembers').insert({
                'roomid': room_id,
                'userid': int(uid)
            }).execute()

    flash('Tạo phòng thành công!', 'success')
    return redirect(url_for('chat'))

@app.route('/search_users')
def search_users():
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({"users": []}), 200
    
    try:
        users_res = supabase_client.table('users').select('userid, username, avatar_url, is_online').ilike('username', f'%{query}%').neq('username', session['user']).limit(10).execute()
        
        users = users_res.data if users_res.data else []
        return jsonify({"users": users}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_my_userid')
def get_my_userid():
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    my_id = my_res.data[0]['userid'] if my_res.data else None
    
    if my_id:
        return jsonify({"userid": my_id}), 200
    else:
        return jsonify({"error": "User not found"}), 404

# ==================== GROUP CHAT ====================

@app.route('/group_chat/<int:roomid>')
def group_chat(roomid):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    my_id = my_res.data[0]['userid'] if my_res.data else None
    if not my_id:
        flash('Không tìm thấy thông tin người dùng!', 'error')
        return redirect(url_for('chat'))
        
    room_res = supabase_client.table('chatrooms').select('*').eq('roomid', roomid).execute()
    if not room_res.data:
        flash('Không tìm thấy phòng chat!', 'error')
        return redirect(url_for('chat'))
    room = room_res.data[0]
    
    member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', roomid).eq('userid', my_id).execute()
    if not member_check.data:
        flash('Bạn không phải thành viên của phòng chat này!', 'error')
        return redirect(url_for('chat'))
    
    messages = []
    msg_res = supabase_client.table('chatroommessages').select('*, file_attachment').eq('roomid', roomid).order('createdat', desc=False).limit(50).execute()
    
    if msg_res.data:
        user_ids = list(set(msg['userid'] for msg in msg_res.data))
        users_res = supabase_client.table('users').select('userid, username, avatar_url').in_('userid', user_ids).execute()
        users = {user['userid']: {'username': user['username'], 'avatar_url': user.get('avatar_url')} for user in (users_res.data or [])}
        
        messages = [{
            **msg,
            'username': users.get(msg['userid'], {}).get('username', 'Unknown User'),
            'avatar_url': users.get(msg['userid'], {}).get('avatar_url')
        } for msg in msg_res.data]
    
    return render_template('group_chat.html', room=room, messages=messages, my_id=my_id)

@app.route('/group_chat/send/<int:roomid>', methods=['POST'])
def send_group_message(roomid):
    if 'user' not in session:
        return jsonify({"error": "Vui lòng đăng nhập lại"}), 401
        
    try:
        my_res = supabase_client.table('users').select('userid, username, avatar_url').eq('username', session['user']).execute()
        if not my_res.data:
            return jsonify({"error": "User not found"}), 400
            
        my_id = my_res.data[0]['userid']
        my_username = my_res.data[0]['username']
        my_avatar = my_res.data[0].get('avatar_url')
            
        member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', roomid).eq('userid', my_id).execute()
        if not member_check.data:
            return jsonify({"error": "Not a member of this room"}), 403
            
        content = request.form.get('content', '').strip()
        if not content:
            return jsonify({"error": "Empty message"}), 400
            
        message_data = {
            'userid': my_id,
            'roomid': roomid,
            'content': content,
            'createdat': get_vietnam_time()
        }
        
        res = supabase_client.table('chatroommessages').insert(message_data).execute()
        
        if res.data:
            response_data = {
                "success": True,
                "message": {
                    **res.data[0],
                    'username': my_username,
                    'userid': my_id,
                    'avatar_url': my_avatar
                }
            }
            return jsonify(response_data), 200
            
        return jsonify({"error": "Failed to save message"}), 500
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/group_chat/messages/<int:roomid>')
def get_group_messages(roomid):
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
        
    try:
        my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        my_id = my_res.data[0]['userid'] if my_res.data else None
        if not my_id:
            return jsonify({"error": "User not found"}), 400
            
        member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', roomid).eq('userid', my_id).execute()
        if not member_check.data:
            return jsonify({"error": "Not a member of this room"}), 403
            
        after_id = request.args.get('after', '0')
        msg_res = supabase_client.table('chatroommessages').select('*').eq('roomid', roomid).gt('messageid', after_id).order('createdat', desc=False).limit(50).execute()
        
        messages = []
        if msg_res.data:
            user_ids = list(set(msg['userid'] for msg in msg_res.data))
            users_res = supabase_client.table('users').select('userid, username, avatar_url').in_('userid', user_ids).execute()
            users = {user['userid']: {'username': user['username'], 'avatar_url': user.get('avatar_url')} for user in (users_res.data or [])}
            
            messages = [{
                **msg,
                'userid': msg['userid'],
                'username': users.get(msg['userid'], {}).get('username', 'Unknown User'),
                'avatar_url': users.get(msg['userid'], {}).get('avatar_url')
            } for msg in msg_res.data]
            
        return jsonify({"messages": messages}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete_group_messages/<int:roomid>', methods=['POST'])
def delete_group_messages(roomid):
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        my_id = my_res.data[0]['userid'] if my_res.data else None
        if not my_id:
            return jsonify({"error": "User not found"}), 400
        
        member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', roomid).eq('userid', my_id).execute()
        if not member_check.data:
            return jsonify({"error": "Not a member of this room"}), 403
        
        supabase_client.table('chatroommessages').delete().eq('roomid', roomid).execute()
        
        return jsonify({"success": True, "message": "Đã xóa tất cả tin nhắn"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== PRIVATE CHAT ====================

@app.route('/private_chat/<int:userid>', methods=['GET', 'POST'])
def private_chat(userid):
    if 'user' not in session:
        return redirect(url_for('login'))
    user_res = supabase_client.table('users').select('username').eq('userid', userid).execute()
    chat_user = user_res.data[0]['username'] if user_res.data else 'Unknown'
    my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    my_id = my_res.data[0]['userid'] if my_res.data else None
    if request.method == 'POST' and my_id:
        try:
            content = request.form.get('message', '').strip()
            if not content:
                content = request.form.get('content', '').strip()
            if content:
                res = supabase_client.table('privatemessages').insert({
                    'senderid': my_id,
                    'receiverid': userid,
                    'content': content,
                    'createdat': get_vietnam_time()
                }).execute()
                if res.data:
                    if request.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                        return jsonify({"success": True, "message": res.data[0]}), 200
                    flash('Gửi tin nhắn thành công', 'success')
                else:
                    if request.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                        return jsonify({"success": False, "error": "Không thể lưu tin nhắn"}), 500
                    flash('Không thể lưu tin nhắn', 'error')
            else:
                if request.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                    return jsonify({"success": False, "error": "Tin nhắn trống"}), 400
                flash('Tin nhắn không được để trống', 'error')
        except Exception as e:
            if request.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                return jsonify({"success": False, "error": str(e)}), 500
            flash('Có lỗi khi gửi tin nhắn', 'error')
    messages = []
    if my_id:
        logic = f"and(senderid.eq.{my_id},receiverid.eq.{userid}),and(senderid.eq.{userid},receiverid.eq.{my_id})"
        msg_res = supabase_client.table('privatemessages').select('*').or_(logic).order('createdat', desc=False).limit(50).execute()
        if msg_res.data:
            # Get all unique sender IDs
            sender_ids = set()
            for msg in msg_res.data:
                sender_ids.add(msg['senderid'])
            
            # Get user information for all senders
            users_res = supabase_client.table('users').select('userid, username, avatar_url').in_('userid', list(sender_ids)).execute()
            user_info = {user['userid']: user for user in users_res.data} if users_res.data else {}
            
            for msg in msg_res.data:
                # Add user information to message
                sender_info = user_info.get(msg['senderid'], {})
                msg['username'] = sender_info.get('username', 'Unknown')
                msg['avatar_url'] = sender_info.get('avatar_url')
                messages.append(msg)
    print(f"[DEBUG] Rendering private_chat: chat_user={chat_user}, userid={userid}, my_id={my_id}")
    return render_template('private_chat.html', chat_user=chat_user, messages=messages, userid=userid, my_id=my_id)

@app.route('/private_chat/messages/<int:userid>')
def get_private_messages(userid):
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    my_id = my_res.data[0]['userid'] if my_res.data else None
    if not my_id:
        return jsonify({"error": "Missing user id"}), 400
    logic = f"and(senderid.eq.{my_id},receiverid.eq.{userid}),and(senderid.eq.{userid},receiverid.eq.{my_id})"
    msg_res = supabase_client.table('privatemessages').select('*').or_(logic).order('createdat', desc=False).limit(50).execute()
    messages = []
    if msg_res.data:
        # Get all unique sender IDs
        sender_ids = set()
        for msg in msg_res.data:
            sender_ids.add(msg['senderid'])
        
        # Get user information for all senders
        users_res = supabase_client.table('users').select('userid, username, avatar_url').in_('userid', list(sender_ids)).execute()
        user_info = {user['userid']: user for user in users_res.data} if users_res.data else {}
        
        for msg in msg_res.data:
            msg['messageid'] = msg.get('messageid') or msg.get('MessageID')
            # Add user information to message
            sender_info = user_info.get(msg['senderid'], {})
            msg['username'] = sender_info.get('username', 'Unknown')
            msg['avatar_url'] = sender_info.get('avatar_url')
            messages.append(msg)
    return jsonify({"messages": messages}), 200

@app.route('/private_chat/send/<int:userid>', methods=['POST'])
def send_private_message(userid):
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    try:
        my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        my_id = my_res.data[0]['userid'] if my_res.data else None
        if not my_id:
            return jsonify({"error": "Missing user id"}), 400
            
        content = request.form.get('content', '').strip()
        if not content:
            return jsonify({"error": "Empty message"}), 400
            
        res = supabase_client.table('privatemessages').insert({
            'senderid': my_id,
            'receiverid': userid,
            'content': content,
            'createdat': get_vietnam_time()
        }).execute()
        
        if res.data:
            return jsonify({"success": True, "message": res.data[0]}), 200
        return jsonify({"error": "Failed to save message"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete_private_messages/<int:userid>', methods=['POST'])
def delete_private_messages(userid):
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        my_id = my_res.data[0]['userid'] if my_res.data else None
        if not my_id:
            return jsonify({"error": "User not found"}), 400
        
        supabase_client.table('privatemessages').delete().eq('senderid', my_id).eq('receiverid', userid).execute()
        supabase_client.table('privatemessages').delete().eq('senderid', userid).eq('receiverid', my_id).execute()
        
        return jsonify({"success": True, "message": "Đã xóa tất cả tin nhắn riêng"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== FILE SHARING IN CHAT ====================

@app.route('/get_my_files')
def get_my_files():
    """Lấy danh sách file của user để share"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        # Lấy file public và private của user
        files = storage_service.list_files(
            current_user=session['user'],
            public_only=False
        )
        
        # Format cho dropdown
        file_list = []
        for file in files:
            metadata = file.get('metadata', {})
            file_list.append({
                'filename': file['name'],
                'original_filename': metadata.get('original_filename', file['name']),
                'size': metadata.get('size_display', 'N/A'),
                'visibility': 'Công khai' if metadata.get('is_public') else 'Riêng tư'
            })
        
        return jsonify({"files": file_list}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload_chat_file', methods=['POST'])
def upload_chat_file():
    """Upload file mới từ chat"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Read file content
    file_content = file.read()
    if len(file_content) == 0:
        return jsonify({"error": "Empty file"}), 400

    filename = file.filename
    # If it's a .docx file, save it as .doc
    if filename.lower().endswith('.docx'):
        # Change the extension to .doc
        filename = os.path.splitext(filename)[0] + '.doc'
        content_type = 'application/msword'
    else:
        # Regular MIME type detection
        content_type = file.content_type
    if not content_type or content_type == 'application/octet-stream':
        # Try to detect MIME type from file extension
        guessed_type, _ = mimetypes.guess_type(file.filename)
        if guessed_type:
            content_type = guessed_type
        else:
            # Check for common office document extensions
            ext = os.path.splitext(file.filename)[1].lower()
            if ext == '.docx':
                content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif ext == '.doc':
                content_type = 'application/msword'
            elif ext == '.xlsx':
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif ext == '.pptx':
                content_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            else:
                # For unknown extensions, use generic binary type
                content_type = 'application/octet-stream'
    
    # File từ chat luôn là riêng tư để bảo mật
    visibility = request.form.get('visibility', 'private')
    is_public = visibility == 'public'
    
    # Upload file
    success = storage_service.upload_file(
        file_content,
        file.filename,
        content_type,
        session['user'],
        is_public
    )
    
    if isinstance(success, dict) and success.get('success'):
        # Lấy thông tin file vừa upload
        files = storage_service.list_files(
            current_user=session['user'],
            public_only=False
        )
        
        # Tìm file vừa upload
        uploaded_file = None
        for f in files:
            metadata = f.get('metadata', {})
            if metadata.get('original_filename') == file.filename:
                uploaded_file = {
                    'filename': f['name'],
                    'original_filename': metadata.get('original_filename'),
                    'size': metadata.get('size_display'),
                    'url': url_for('download', filename=f['name'], _external=True)
                }
                break
        
        return jsonify({
            "success": True,
            "file": uploaded_file
        }), 200
    else:
        error_msg = success.get('error', 'Upload failed') if isinstance(success, dict) else 'Upload failed'
        return jsonify({"error": error_msg}), 500

@app.route('/share_file_to_chat', methods=['POST'])
def share_file_to_chat():
    """Share file đã có vào chat"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json()
    filename = data.get('filename')
    chat_type = data.get('chat_type')  # 'group' or 'private'
    chat_id = data.get('chat_id')
    
    if not all([filename, chat_type, chat_id]):
        return jsonify({"error": "Missing parameters"}), 400
    
    try:
        # Lấy thông tin file
        files = storage_service.list_files(
            current_user=session['user'],
            public_only=False
        )
        
        file_info = None
        for f in files:
            if f['name'] == filename:
                metadata = f.get('metadata', {})
                file_info = {
                    'filename': f['name'],
                    'original_filename': metadata.get('original_filename'),
                    'size': metadata.get('size_display'),
                    'url': url_for('download', filename=f['name'], _external=True),
                    'preview_url': url_for('preview', filename=f['name'], _external=True)
                }
                break
        
        if not file_info:
            return jsonify({"error": "File not found"}), 404
        
        # Lấy user ID
        my_res = supabase_client.table('users').select('userid, username, avatar_url').eq('username', session['user']).execute()
        if not my_res.data:
            return jsonify({"error": "User not found"}), 400
        
        my_id = my_res.data[0]['userid']
        my_username = my_res.data[0]['username']
        my_avatar = my_res.data[0].get('avatar_url')
        
        # Tạo message với file attachment
        message_content = f"📎 Đã chia sẻ file: {file_info['original_filename']}"
        
        if chat_type == 'group':
            # Send to group
            res = supabase_client.table('chatroommessages').insert({
                'userid': my_id,
                'roomid': int(chat_id),
                'content': message_content,
                'file_attachment': file_info,
                'createdat': get_vietnam_time()
            }).execute()
            
            if res.data:
                return jsonify({
                    "success": True,
                    "message": {
                        **res.data[0],
                        'username': my_username,
                        'avatar_url': my_avatar,
                        'file_attachment': file_info
                    }
                }), 200
        else:
            # Send to private chat
            res = supabase_client.table('privatemessages').insert({
                'senderid': my_id,
                'receiverid': int(chat_id),
                'content': message_content,
                'file_attachment': file_info,
                'createdat': get_vietnam_time()
            }).execute()
            
            if res.data:
                return jsonify({
                    "success": True,
                    "message": {
                        **res.data[0],
                        'username': my_username,
                        'avatar_url': my_avatar,
                        'file_attachment': file_info
                    }
                }), 200
        
        return jsonify({"error": "Failed to send"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/chat_file_access/<filename>')
def chat_file_access(filename):
    """Kiểm tra quyền truy cập file trong chat"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        # Lấy thông tin file từ metadata
        metadata_resp = supabase_client.table('files_metadata').select('metadata').eq('filename', filename).execute()
        if not metadata_resp.data:
            return jsonify({"error": "File not found"}), 404
        
        metadata = metadata_resp.data[0].get('metadata', {})
        file_owner = metadata.get('uploaded_by')
        
        # Kiểm tra nếu user là chủ sở hữu file
        if file_owner == session['user']:
            return jsonify({"access": "owner"}), 200
        
        # Kiểm tra nếu file được chia sẻ trong chat với user này
        # Tìm trong private messages
        private_msgs = supabase_client.table('privatemessages').select('*').contains('file_attachment', {'filename': filename}).execute()
        if private_msgs.data:
            for msg in private_msgs.data:
                # Kiểm tra nếu user là sender hoặc receiver
                if msg['senderid'] == get_user_id(session['user']) or msg['receiverid'] == get_user_id(session['user']):
                    return jsonify({"access": "shared"}), 200
        
        # Tìm trong group messages
        group_msgs = supabase_client.table('chatroommessages').select('*').contains('file_attachment', {'filename': filename}).execute()
        if group_msgs.data:
            for msg in group_msgs.data:
                # Kiểm tra nếu user là thành viên của room
                member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', msg['roomid']).eq('userid', get_user_id(session['user'])).execute()
                if member_check.data:
                    return jsonify({"access": "shared"}), 200
        
        return jsonify({"error": "Access denied"}), 403
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_user_id(username):
    """Helper function to get user ID"""
    try:
        res = supabase_client.table('users').select('userid').eq('username', username).execute()
        return res.data[0]['userid'] if res.data else None
    except:
        return None


def redirect_back(default='index'):
    """Redirect back to referrer or next param, otherwise to default endpoint."""
    from flask import request
    # Prefer explicit 'next' parameter
    next_page = request.args.get('next') or request.form.get('next')
    if next_page:
        return redirect(next_page)
    # Then referrer
    ref = request.referrer
    if ref:
        return redirect(ref)
    return redirect(url_for(default))

# Group Management Routes
@app.route('/group_settings/<int:roomid>')
def group_settings(roomid):
    """Trang chỉnh sửa thông tin nhóm"""
    if 'user' not in session:
        return redirect(url_for('login', next=request.url))
    
    try:
        print(f"Accessing group_settings for roomid: {roomid}, user: {session['user']}")
        # Lấy thông tin nhóm với retry
        def get_room():
            return supabase_client.table('chatrooms').select('*').eq('roomid', roomid).execute()
        
        room_res = retry_supabase_operation(get_room)
        if not room_res.data:
            flash('Nhóm không tồn tại', 'error')
            return redirect(url_for('chat'))
        
        room = room_res.data[0]
        
        # Lấy thông tin người upload avatar nếu có
        if room.get('avatar_uploaded_by'):
            try:
                uploader_res = supabase_client.table('users').select('username, avatar_url').eq('userid', room['avatar_uploaded_by']).execute()
                if uploader_res.data:
                    room['avatar_uploader'] = uploader_res.data[0]
            except:
                room['avatar_uploader'] = None
        else:
            room['avatar_uploader'] = None
        
        # Format avatar_uploaded_at nếu có
        if room.get('avatar_uploaded_at'):
            try:
                from datetime import datetime
                if isinstance(room['avatar_uploaded_at'], str):
                    # Parse ISO string to datetime
                    dt = datetime.fromisoformat(room['avatar_uploaded_at'].replace('Z', '+00:00'))
                    room['avatar_uploaded_at'] = dt.strftime('%d/%m/%Y %H:%M')
                else:
                    # Already a datetime object
                    room['avatar_uploaded_at'] = room['avatar_uploaded_at'].strftime('%d/%m/%Y %H:%M')
            except:
                # If parsing fails, keep original value
                pass
        
        # Lấy userid từ session với retry
        def get_current_user():
            return supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        
        current_user_res = retry_supabase_operation(get_current_user)
        if not current_user_res.data:
            flash('Không tìm thấy thông tin người dùng', 'error')
            return redirect(url_for('chat'))
        
        current_userid = current_user_res.data[0]['userid']
        
        # Lưu userid vào session để template có thể sử dụng
        session['userid'] = current_userid
        
        # Kiểm tra user có phải là người tạo nhóm không
        is_room_creator = room.get('createdby') == current_userid
        
        # Kiểm tra user có phải là thành viên nhóm không với retry
        def check_member():
            return supabase_client.table('chatroommembers').select('*').eq('roomid', roomid).eq('userid', current_userid).execute()
        
        member_res = retry_supabase_operation(check_member)
        if not member_res.data:
            flash('Bạn không phải thành viên nhóm này', 'error')
            return redirect(url_for('chat'))
        
        # Lấy danh sách thành viên (không dùng JOIN)
        def get_members():
            return supabase_client.table('chatroommembers').select('userid, joinedat').eq('roomid', roomid).execute()

        members_res = retry_supabase_operation(get_members)

        # Debug log
        print(f"📊 Members query result: {len(members_res.data) if members_res.data else 0} members")

        members = []
        for member in members_res.data:
            # Lấy thông tin user riêng lẻ
            try:
                user_res = supabase_client.table('users').select('username, avatar_url, is_online, last_seen').eq('userid', member['userid']).execute()

                if not user_res.data:
                    print(f"⚠️ Warning: User not found for userid: {member['userid']}")
                    continue

                user_data = user_res.data[0]

                # Format last_seen nếu có
                last_seen = user_data.get('last_seen')
                if last_seen:
                    try:
                        from datetime import datetime
                        if isinstance(last_seen, str):
                            # Parse ISO string to datetime
                            dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                            last_seen = dt.strftime('%d/%m/%Y %H:%M')
                        else:
                            # Already a datetime object
                            last_seen = last_seen.strftime('%d/%m/%Y %H:%M')
                    except:
                        # If parsing fails, keep original value
                        pass

                members.append({
                    'userid': member['userid'],
                    'username': user_data.get('username', 'Unknown'),
                    'avatar_url': user_data.get('avatar_url'),
                    'is_online': user_data.get('is_online', False),
                    'last_seen': last_seen,
                    'joined_at': member.get('joinedat')
                })
            except Exception as e:
                print(f"❌ Error fetching user data for userid {member['userid']}: {str(e)}")
                continue
        
        return render_template('group_settings.html', room=room, members=members, is_room_creator=is_room_creator)
    
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('chat'))

@app.route('/update_group_info', methods=['POST'])
def update_group_info():
    """Cập nhật thông tin nhóm"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        data = request.get_json()
        roomid = data.get('roomid')
        roomname = data.get('roomname', '').strip()
        
        if not roomname:
            return jsonify({"error": "Tên nhóm không được để trống"}), 400
        
        # Lấy userid từ session
        current_user_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        if not current_user_res.data:
            return jsonify({"error": "Không tìm thấy thông tin người dùng"}), 401
        
        current_userid = current_user_res.data[0]['userid']
        
        # Kiểm tra quyền (chỉ thành viên mới được cập nhật)
        member_res = supabase_client.table('chatroommembers').select('userid').eq('roomid', roomid).eq('userid', current_userid).execute()
        if not member_res.data:
            return jsonify({"error": "Bạn không có quyền chỉnh sửa nhóm này"}), 403
        
        # Cập nhật tên nhóm
        update_res = supabase_client.table('chatrooms').update({
            'roomname': roomname
        }).eq('roomid', roomid).execute()
        
        if update_res.data:
            return jsonify({"success": True, "message": "Đã cập nhật thông tin nhóm"})
        else:
            return jsonify({"error": "Lỗi khi cập nhật thông tin nhóm"}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload_group_avatar', methods=['POST'])
def upload_group_avatar():
    """Upload ảnh đại diện nhóm"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        roomid = request.form.get('roomid')
        if not roomid:
            return jsonify({"error": "Room ID is required"}), 400
        
        # Lấy userid từ session
        current_user_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        if not current_user_res.data:
            return jsonify({"error": "Không tìm thấy thông tin người dùng"}), 401
        
        current_userid = current_user_res.data[0]['userid']
        
        # Kiểm tra quyền
        member_res = supabase_client.table('chatroommembers').select('userid').eq('roomid', roomid).eq('userid', current_userid).execute()
        if not member_res.data:
            return jsonify({"error": "Bạn không có quyền chỉnh sửa nhóm này"}), 403
        
        # Upload file to avatars bucket
        file_content = file.read()
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        filename = f"group_{roomid}_{int(time.time())}.{file_extension}"
        
        try:
            upload_res = supabase_client.storage.from_('avatars').upload(filename, file_content, {
                'content-type': file.content_type or 'image/jpeg'
            })
            
            # Kiểm tra lỗi upload
            if hasattr(upload_res, 'error') and upload_res.error:
                print(f"Upload error: {upload_res.error}")
                return jsonify({"error": f"Upload failed: {upload_res.error}"}), 500
            
            # Lấy URL public
            avatar_url = supabase_client.storage.from_('avatars').get_public_url(filename)
            
        except Exception as upload_error:
            print(f"Storage upload error: {str(upload_error)}")
            return jsonify({"error": f"Storage error: {str(upload_error)}"}), 500
        
        # Cập nhật avatar_url và thông tin người upload
        try:
            update_res = supabase_client.table('chatrooms').update({
                'avatar_url': avatar_url,
                'avatar_uploaded_by': current_userid,
                'avatar_uploaded_at': get_vietnam_time()
            }).eq('roomid', roomid).execute()
            
            if update_res.data:
                return jsonify({
                    "success": True, 
                    "avatar_url": avatar_url,
                    "message": "Đã cập nhật ảnh đại diện nhóm"
                })
            else:
                return jsonify({"error": "Lỗi khi cập nhật ảnh đại diện trong database"}), 500
                
        except Exception as db_error:
            print(f"Database update error: {str(db_error)}")
            return jsonify({"error": f"Database error: {str(db_error)}"}), 500
    
    except Exception as e:
        print(f"Upload group avatar error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/leave_group', methods=['POST'])
def leave_group():
    """Rời khỏi nhóm"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        data = request.get_json()
        roomid = data.get('roomid')
        
        # Lấy userid từ session
        current_user_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        if not current_user_res.data:
            return jsonify({"error": "Không tìm thấy thông tin người dùng"}), 401
        
        current_userid = current_user_res.data[0]['userid']
        
        # Kiểm tra user có phải là thành viên nhóm không
        member_res = supabase_client.table('chatroommembers').select('userid').eq('roomid', roomid).eq('userid', current_userid).execute()
        if not member_res.data:
            return jsonify({"error": "Bạn không phải thành viên nhóm này"}), 403
        
        # Kiểm tra user có phải là người tạo nhóm không
        room_res = supabase_client.table('chatrooms').select('createdby').eq('roomid', roomid).execute()
        if room_res.data and room_res.data[0]['createdby'] == current_userid:
            return jsonify({"error": "Người tạo nhóm không thể rời nhóm. Hãy xóa nhóm thay vào đó."}), 400
        
        # Xóa thành viên khỏi nhóm
        remove_res = supabase_client.table('chatroommembers').delete().eq('roomid', roomid).eq('userid', current_userid).execute()
        
        if remove_res.data:
            return jsonify({"success": True, "message": "Đã rời khỏi nhóm"})
        else:
            return jsonify({"error": "Lỗi khi rời nhóm"}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete_group', methods=['POST'])
def delete_group():
    """Xóa nhóm (chỉ người tạo)"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        data = request.get_json()
        roomid = data.get('roomid')
        
        # Lấy userid từ session
        current_user_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        if not current_user_res.data:
            return jsonify({"error": "Không tìm thấy thông tin người dùng"}), 401
        
        current_userid = current_user_res.data[0]['userid']
        
        # Kiểm tra user có phải là người tạo nhóm không
        room_res = supabase_client.table('chatrooms').select('createdby').eq('roomid', roomid).execute()
        if not room_res.data:
            return jsonify({"error": "Nhóm không tồn tại"}), 404
        
        if room_res.data[0]['createdby'] != current_userid:
            return jsonify({"error": "Chỉ người tạo nhóm mới có thể xóa nhóm"}), 403
        
        # Xóa tất cả thành viên nhóm
        supabase_client.table('chatroommembers').delete().eq('roomid', roomid).execute()
        
        # Xóa tất cả tin nhắn nhóm
        supabase_client.table('groupmessages').delete().eq('roomid', roomid).execute()
        
        # Xóa nhóm
        delete_res = supabase_client.table('chatrooms').delete().eq('roomid', roomid).execute()
        
        if delete_res.data:
            return jsonify({"success": True, "message": "Đã xóa nhóm thành công"})
        else:
            return jsonify({"error": "Lỗi khi xóa nhóm"}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_group_member', methods=['POST'])
def add_group_member():
    """Thêm thành viên vào nhóm"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        data = request.get_json()
        roomid = data.get('roomid')
        username = data.get('username', '').strip()
        
        if not username:
            return jsonify({"error": "Tên người dùng không được để trống"}), 400
        
        # Lấy userid từ session
        current_user_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        if not current_user_res.data:
            return jsonify({"error": "Không tìm thấy thông tin người dùng"}), 401
        
        current_userid = current_user_res.data[0]['userid']
        
        # Kiểm tra quyền (chỉ thành viên mới được thêm người)
        member_res = supabase_client.table('chatroommembers').select('userid').eq('roomid', roomid).eq('userid', current_userid).execute()
        if not member_res.data:
            return jsonify({"error": "Bạn không có quyền thêm thành viên"}), 403
        
        # Tìm user
        user_res = supabase_client.table('users').select('userid').eq('username', username).execute()
        if not user_res.data:
            return jsonify({"error": "Người dùng không tồn tại"}), 404
        
        new_userid = user_res.data[0]['userid']
        
        # Kiểm tra đã là thành viên chưa
        existing_res = supabase_client.table('chatroommembers').select('userid').eq('roomid', roomid).eq('userid', new_userid).execute()
        if existing_res.data:
            return jsonify({"error": "Người này đã là thành viên nhóm"}), 400
        
        # Thêm thành viên
        add_res = supabase_client.table('chatroommembers').insert({
            'roomid': roomid,
            'userid': new_userid
        }).execute()
        
        if add_res.data:
            return jsonify({"success": True, "message": f"Đã thêm {username} vào nhóm"})
        else:
            return jsonify({"error": "Lỗi khi thêm thành viên"}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/remove_group_member', methods=['POST'])
def remove_group_member():
    """Xóa thành viên khỏi nhóm (chỉ người tạo nhóm mới có quyền)"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401

    try:
        data = request.get_json()
        roomid = data.get('roomid')
        userid_to_remove = data.get('userid')

        # Lấy userid từ session
        current_user_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        if not current_user_res.data:
            return jsonify({"error": "Không tìm thấy thông tin người dùng"}), 401

        current_userid = current_user_res.data[0]['userid']

        # Kiểm tra user có phải là người tạo nhóm không
        room_res = supabase_client.table('chatrooms').select('createdby').eq('roomid', roomid).execute()
        if not room_res.data:
            return jsonify({"error": "Nhóm không tồn tại"}), 404

        room_creator = room_res.data[0].get('createdby')

        # Chỉ người tạo nhóm mới có quyền kick member
        if room_creator != current_userid:
            return jsonify({"error": "Chỉ người tạo nhóm mới có quyền xóa thành viên"}), 403

        # Không cho phép xóa chính mình (người tạo)
        if int(userid_to_remove) == current_userid:
            return jsonify({"error": "Bạn không thể xóa chính mình khỏi nhóm. Hãy dùng chức năng 'Xóa nhóm' thay thế."}), 400

        # Xóa thành viên
        remove_res = supabase_client.table('chatroommembers').delete().eq('roomid', roomid).eq('userid', userid_to_remove).execute()

        if remove_res:
            return jsonify({"success": True, "message": "Đã xóa thành viên khỏi nhóm"})
        else:
            return jsonify({"error": "Lỗi khi xóa thành viên"}), 500

    except Exception as e:
        print(f"❌ Error in remove_group_member: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Private Chat Info Routes
@app.route('/private_chat_info/<int:userid>')
def private_chat_info(userid):
    """Trang thông tin chat riêng tư"""
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        # Defensive logging
        print(f"[DEBUG] Enter private_chat_info with raw userid={userid} (type={type(userid)})")

        # Ensure userid is integer
        try:
            userid = int(userid)
        except Exception as conv_err:
            msg = f"Invalid userid value: {userid} ({conv_err})"
            print(f"[ERROR] {msg}")
            # Return visible error so developer can see it in browser
            return Response(f"<h3>Invalid userid</h3><pre>{msg}</pre>", mimetype='text/html', status=400)

        # Lấy thông tin người dùng hiện tại (with retry)
        def fetch_current_user():
            return supabase_client.table('users').select('userid').eq('username', session['user']).execute()

        current_user_res = execute_with_retries(fetch_current_user)
        if not current_user_res or not getattr(current_user_res, 'data', None):
            msg = 'Không tìm thấy thông tin người dùng (current user)'
            print(f"[ERROR] {msg}")
            return Response(f"<h3>User not found</h3><pre>{msg}</pre>", mimetype='text/html', status=404)

        current_userid = current_user_res.data[0]['userid']

        # Lấy thông tin người chat
        # Fetch chat user (with retry)
        def fetch_chat_user():
            return supabase_client.table('users').select('*').eq('userid', userid).execute()

        chat_user_res = execute_with_retries(fetch_chat_user)
        if not chat_user_res or not getattr(chat_user_res, 'data', None):
            msg = f'Người dùng không tồn tại: userid={userid}'
            print(f"[ERROR] {msg}")
            return Response(f"<h3>User not found</h3><pre>{msg}</pre>", mimetype='text/html', status=404)

        chat_user = chat_user_res.data[0]

        # Normalize last_seen to a datetime object if it's a string so template can call strftime()
        try:
            last_seen = chat_user.get('last_seen')
            if last_seen and isinstance(last_seen, str):
                # Handle ISO format possibly ending with Z
                try:
                    chat_user['last_seen'] = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                except Exception:
                    # fallback: try parsing common formats
                    try:
                        chat_user['last_seen'] = datetime.strptime(last_seen, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        # leave as string if parsing fails
                        pass
        except Exception as e:
            print(f"[WARN] Could not normalize chat_user.last_seen: {e}")

        # Lấy danh sách file đã gửi trong cuộc trò chuyện (defensive)
        files_sent = []
        try:
            def fetch_files_sent():
                return supabase_client.table('privatemessages').select('file_attachment').eq('senderid', current_userid).eq('receiverid', userid).not_.is_('file_attachment', 'null').execute()
            files_res = execute_with_retries(fetch_files_sent)
            if files_res and getattr(files_res, 'data', None):
                for msg in files_res.data:
                    if msg and msg.get('file_attachment'):
                        files_sent.append(msg['file_attachment'])
        except Exception as e:
            print(f"[WARN] Could not fetch files_sent after retries: {e}")

        # Lấy file nhận được
        files_received = []
        try:
            def fetch_files_received():
                return supabase_client.table('privatemessages').select('file_attachment').eq('senderid', userid).eq('receiverid', current_userid).not_.is_('file_attachment', 'null').execute()
            files_received_res = execute_with_retries(fetch_files_received)
            if files_received_res and getattr(files_received_res, 'data', None):
                for msg in files_received_res.data:
                    if msg and msg.get('file_attachment'):
                        files_received.append(msg['file_attachment'])
        except Exception as e:
            print(f"[WARN] Could not fetch files_received after retries: {e}")

        # Render
        return render_template('private_chat_info.html', 
                             chat_user=chat_user, 
                             files_sent=files_sent, 
                             files_received=files_received)
    except Exception as e:
        # Final catch: return error page with debug info rather than silent redirect
        print(f"[EXCEPTION] private_chat_info failed: {e}")
        import traceback
        tb = traceback.format_exc()
        return Response(f"<h3>Exception in private_chat_info</h3><pre>{tb}</pre>", mimetype='text/html', status=500)

@app.route('/set_nickname', methods=['POST'])
def set_nickname():
    """Đặt biệt danh cho người dùng"""
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        data = request.get_json()
        target_userid = data.get('target_userid')
        nickname = data.get('nickname', '').strip()
        
        if not target_userid:
            return jsonify({"error": "Target user ID is required"}), 400
        
        
        return jsonify({"success": True, "message": "Đã đặt biệt danh"})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# N8N Webhook URL - Thay bằng URL webhook của bạn
N8N_WEBHOOK_URL = "https://n8n.vtcmobile.vn/webhook/send-otp"
N8N_SUCCESS_WEBHOOK_URL = "https://n8n.vtcmobile.vn/webhook/registration-success"  # Webhook mới cho email thành công
N8N_DELETE_FILE_WEBHOOK_URL = "https://n8n.vtcmobile.vn/webhook/file-deleted"
N8N_UPLOAD_FILE_WEBHOOK_URL = "https://n8n.vtcmobile.vn/webhook/file-uploaded"
N8N_FORGOT_PASSWORD_WEBHOOK_URL = "https://n8n.vtcmobile.vn/webhook/forgot-password"  # Webhook cho quên mật khẩu

def validate_email(email):
    """Kiểm tra định dạng email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Kiểm tra mật khẩu mạnh: 
    - Ít nhất 8 ký tự
    - Có chữ hoa, chữ thường, số
    """
    if len(password) < 8:
        return False, "Mật khẩu phải có ít nhất 8 ký tự"
    
    if not re.search(r'[A-Z]', password):
        return False, "Mật khẩu phải có ít nhất 1 chữ hoa"
    
    if not re.search(r'[a-z]', password):
        return False, "Mật khẩu phải có ít nhất 1 chữ thường"
    
    if not re.search(r'[0-9]', password):
        return False, "Mật khẩu phải có ít nhất 1 chữ số"
    
    return True, "OK"

def generate_otp():
    """Tạo mã OTP 6 số"""
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def send_otp_via_n8n(email, otp_code, username):
    """Gửi OTP qua N8N webhook"""
    try:
        payload = {
            "email": email,
            "otp_code": otp_code,
            "username": username,
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "Email đã được gửi"
        else:
            return False, f"Lỗi gửi email: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, "Timeout khi gửi email"
    except Exception as e:
        return False, f"Lỗi: {str(e)}"

def send_registration_success_email(email, username):
    """Gửi email thông báo đăng ký thành công qua N8N webhook"""
    try:
        payload = {
            "email": email,
            "username": username,
            "timestamp": datetime.now().isoformat(),
            "login_url": "https://your-domain.com/login"  # Thay bằng URL thực tế của bạn
        }
        
        response = requests.post(
            N8N_SUCCESS_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "Email thông báo đã được gửi"
        else:
            return False, f"Lỗi gửi email: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, "Timeout khi gửi email"
    except Exception as e:
        return False, f"Lỗi: {str(e)}"

def send_file_deleted_email(email, username, filename, deleted_by):
    """Gửi email thông báo file đã bị xóa qua N8N webhook"""
    try:
        payload = {
            "email": email,
            "username": username,
            "filename": filename,
            "deleted_by": deleted_by,
            "deleted_at": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(
            N8N_DELETE_FILE_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "Email thông báo đã được gửi"
        else:
            return False, f"Lỗi gửi email: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, "Timeout khi gửi email"
    except Exception as e:
        return False, f"Lỗi: {str(e)}"
    
def send_file_uploaded_email(email, username, filename, filesize, filetype, visibility):
    """Gửi email thông báo file đã được upload qua N8N webhook"""
    try:
        payload = {
            "email": email,
            "username": username,
            "filename": filename,
            "filesize": filesize,
            "filetype": filetype,
            "visibility": visibility,
            "uploaded_at": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(
            N8N_UPLOAD_FILE_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "Email thông báo đã được gửi"
        else:
            return False, f"Lỗi gửi email: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, "Timeout khi gửi email"
    except Exception as e:
        return False, f"Lỗi: {str(e)}"
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('Vui lòng điền đầy đủ thông tin!', 'error')
            return redirect(url_for('register'))
        
        # Validate email
        if not validate_email(email):
            flash('Email không đúng định dạng!', 'error')
            return redirect(url_for('register'))
        
        # Validate password
        is_valid, message = validate_password(password)
        if not is_valid:
            flash(message, 'error')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Mật khẩu không khớp!', 'error')
            return redirect(url_for('register'))
        
        # Kiểm tra username đã tồn tại
        existing_user = supabase_client.table('users').select('username').eq('username', username).execute()
        if existing_user.data:
            flash('Tên đăng nhập đã tồn tại!', 'error')
            return redirect(url_for('register'))
        
        # Kiểm tra email đã tồn tại
        existing_email = supabase_client.table('users').select('email').eq('email', email).execute()
        if existing_email.data:
            flash('Email đã được sử dụng!', 'error')
            return redirect(url_for('register'))
        
        # Kiểm tra pending registration
        pending = supabase_client.table('pending_registrations').select('*').eq('email', email).execute()
        if pending.data:
            # Xóa pending cũ
            supabase_client.table('pending_registrations').delete().eq('email', email).execute()
        
        # Tạo OTP
        otp_code = generate_otp()
        
        # Hash password (sử dụng service của bạn)
        hashed_password = user_service._hash_password(password)
        
        # Lưu vào pending_registrations
        expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()
        
        try:
            supabase_client.table('pending_registrations').insert({
                'username': username,
                'email': email,
                'password': hashed_password,
                'verification_code': otp_code,
                'expires_at': expires_at
            }).execute()
            
            # Gửi OTP qua N8N
            success, message = send_otp_via_n8n(email, otp_code, username)
            
            if success:
                # Lưu email vào session để verify
                session['pending_email'] = email
                session['pending_username'] = username
                flash('Mã xác thực đã được gửi đến email của bạn!', 'success')
                return redirect(url_for('verify_registration'))
            else:
                # Xóa pending nếu gửi email thất bại
                supabase_client.table('pending_registrations').delete().eq('email', email).execute()
                flash(f'Không thể gửi email: {message}', 'error')
                return redirect(url_for('register'))
                
        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/verify-registration', methods=['GET', 'POST'])
def verify_registration():
    if 'pending_email' not in session:
        flash('Vui lòng đăng ký trước!', 'error')
        return redirect(url_for('register'))
    
    if request.method == 'POST':
        otp_code = request.form.get('otp_code', '').strip()
        email = session.get('pending_email')
        username = session.get('pending_username')
        
        if not otp_code or len(otp_code) != 6:
            flash('Mã xác thực phải có 6 chữ số!', 'error')
            return redirect(url_for('verify_registration'))
        
        # Gọi function verify
        try:
            result = supabase_client.rpc('verify_registration_code', {
                'p_email': email,
                'p_code': otp_code
            }).execute()
            # Debug log for RPC response
            print(f"[DEBUG] verify_registration rpc result: {getattr(result, 'data', None)}")

            # Interpret RPC result robustly
            if result.data and len(result.data) > 0:
                verification = result.data[0]
                print(f"[DEBUG] verification payload: {verification}")

                raw_success = verification.get('success')
                success_flag = False
                try:
                    if isinstance(raw_success, bool):
                        success_flag = raw_success
                    elif isinstance(raw_success, int):
                        success_flag = (raw_success != 0)
                    elif raw_success is None:
                        success_flag = False
                    else:
                        success_flag = str(raw_success).lower() in ('1', 'true', 't', 'yes', 'y')
                except Exception:
                    success_flag = bool(raw_success)

                if success_flag:
                    # GỬI EMAIL THÔNG BÁO THÀNH CÔNG
                    try:
                        success, message = send_registration_success_email(email, username)
                        if not success:
                            print(f"Warning: Failed to send success email: {message}")
                    except Exception as e:
                        print(f"Warning: Exception when sending success email: {str(e)}")

                    # Clear session and pending registration
                    try:
                        supabase_client.table('pending_registrations').delete().eq('email', email).execute()
                    except Exception:
                        pass

                    session.pop('pending_email', None)
                    session.pop('pending_username', None)

                    flash('Đăng ký thành công! Bạn có thể đăng nhập ngay. Một email xác nhận đã được gửi đến hộp thư của bạn.', 'success')
                    return redirect(url_for('login'))
                else:
                    # RPC said verification failed; double-check DB — sometimes the DB function may have side-effects
                    try:
                        user_check = supabase_client.table('users').select('*').eq('email', email).execute()
                        if user_check.data:
                            # The account exists in DB — consider confirmation successful
                            try:
                                supabase_client.table('pending_registrations').delete().eq('email', email).execute()
                            except Exception:
                                pass
                            session.pop('pending_email', None)
                            session.pop('pending_username', None)
                            flash('Đăng ký thành công! Bạn có thể đăng nhập ngay. (Được xác nhận trong hệ thống)', 'success')
                            return redirect(url_for('login'))
                    except Exception as e:
                        print(f"[WARN] Error checking users table after RPC failure: {e}")

                    flash(verification.get('message', 'Xác thực thất bại'), 'error')
                    return redirect(url_for('verify_registration'))
            else:
                # No RPC data returned — check if the user was created/activated anyway
                try:
                    user_check = supabase_client.table('users').select('*').eq('email', email).execute()
                    if user_check.data:
                        try:
                            supabase_client.table('pending_registrations').delete().eq('email', email).execute()
                        except Exception:
                            pass
                        session.pop('pending_email', None)
                        session.pop('pending_username', None)
                        flash('Đăng ký thành công! Bạn có thể đăng nhập ngay. (Được xác nhận trong hệ thống)', 'success')
                        return redirect(url_for('login'))
                except Exception as e:
                    print(f"[WARN] Error checking users table when RPC returned no data: {e}")

                flash('Có lỗi xảy ra khi xác thực!', 'error')
                return redirect(url_for('verify_registration'))
                
        except Exception as e:
            flash(f'Lỗi: {str(e)}', 'error')
            return redirect(url_for('verify_registration'))
    
    return render_template('verify_registration.html', 
                         email=session.get('pending_email'))

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Gửi lại mã OTP"""
    if 'pending_email' not in session:
        return jsonify({"error": "Không tìm thấy thông tin đăng ký"}), 400
    
    email = session.get('pending_email')
    username = session.get('pending_username')
    
    try:
        # Lấy pending registration
        pending = supabase_client.table('pending_registrations').select('*').eq('email', email).execute()
        
        if not pending.data:
            return jsonify({"error": "Phiên đăng ký đã hết hạn"}), 400
        
        # Tạo OTP mới
        new_otp = generate_otp()
        expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()
        
        # Cập nhật OTP và reset attempts
        supabase_client.table('pending_registrations').update({
            'verification_code': new_otp,
            'verification_attempts': 0,
            'expires_at': expires_at
        }).eq('email', email).execute()
        
        # Gửi OTP mới
        success, message = send_otp_via_n8n(email, new_otp, username)
        
        if success:
            return jsonify({"success": True, "message": "Đã gửi lại mã xác thực"}), 200
        else:
            return jsonify({"error": message}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    
    