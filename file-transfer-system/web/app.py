from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, Response
import os
from supabase import create_client
import tempfile
import uuid
import re
from datetime import datetime
from services.storage_service import StorageService
from services.user_service import UserService

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Thay đổi thành một key bí mật thực tế

# Cấu hình Supabase
SUPABASE_URL = "https://qrzycoatheltpfiztkeh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFyenljb2F0aGVsdHBmaXp0a2VoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODY3NjA1NiwiZXhwIjoyMDc0MjUyMDU2fQ.3JmRXRDs-QcEQDHNghjTJEPvoEHA3Zx5MpioHTh9rWM"

supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
storage_service = StorageService(supabase_client)
user_service = UserService(supabase_client)

@app.route('/private_chat/<int:userid>', methods=['GET', 'POST'])
def private_chat(userid):
    if 'user' not in session:
        return redirect(url_for('login'))
    # Lấy thông tin user đang chat
    user_res = supabase_client.table('users').select('username').eq('userid', userid).execute()
    chat_user = user_res.data[0]['username'] if user_res.data else 'Unknown'
    # Lấy id của mình
    my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    my_id = my_res.data[0]['userid'] if my_res.data else None
    # Nếu gửi tin nhắn (POST)
    if request.method == 'POST' and my_id:
        try:
            # Hỗ trợ cả gửi từ form truyền thống và AJAX
            content = request.form.get('message', '').strip()
            if not content:
                content = request.form.get('content', '').strip()
            if content:
                # Lưu tin nhắn vào CSDL
                res = supabase_client.table('privatemessages').insert({
                    'senderid': my_id,
                    'receiverid': userid,
                    'content': content,
                    'createdat': datetime.now().isoformat()
                }).execute()
                # Kiểm tra kết quả và trả về response phù hợp
                if res.data:
                    if request.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                        return {"success": True, "message": res.data[0]}, 200
                    flash('Gửi tin nhắn thành công', 'success')
                else:
                    if request.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                        return {"success": False, "error": "Không thể lưu tin nhắn"}, 500
                    flash('Không thể lưu tin nhắn', 'error')
            else:
                if request.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                    return {"success": False, "error": "Tin nhắn trống"}, 400
                flash('Tin nhắn không được để trống', 'error')
        except Exception as e:
            if request.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                return {"success": False, "error": str(e)}, 500
            flash('Có lỗi khi gửi tin nhắn', 'error')
    # Lấy tin nhắn giữa 2 user
    messages = []
    if my_id:
        logic = f"and(senderid.eq.{my_id},receiverid.eq.{userid}),and(senderid.eq.{userid},receiverid.eq.{my_id})"
        msg_res = supabase_client.table('privatemessages').select('*').or_(logic).order('createdat', desc=False).limit(50).execute()
        messages = msg_res.data if msg_res.data else []
    return render_template('private_chat.html', chat_user=chat_user, messages=messages, userid=userid, my_id=my_id)


@app.route('/create_room_page')
def create_room_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    # Get list of users for member selection, excluding current user
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
        
    # Kiểm tra xem phòng đã tồn tại chưa
    exists = supabase_client.table('chatrooms').select('*').eq('roomname', room_name).execute()
    if exists.data:
        flash('Tên phòng đã tồn tại! Vui lòng chọn tên khác.', 'error')
        return redirect(url_for('create_room_page'))
        
    # Tạo phòng chat mới
    try:
        res = supabase_client.table('chatrooms').insert({'roomname': room_name}).execute()
        if not res.data:
            flash('Tạo phòng thất bại!', 'error')
            return redirect(url_for('create_room_page'))
    except Exception as e:
        flash('Có lỗi xảy ra khi tạo phòng: ' + str(e), 'error')
        return redirect(url_for('create_room_page'))
    room_id = res.data[0]['roomid']
    # Thêm thành viên vào phòng
    for uid in member_ids:
        supabase_client.table('chatroommembers').insert({'roomid': room_id, 'userid': int(uid)}).execute()
    # Thêm người tạo phòng vào luôn
    creator = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    if creator.data:
        supabase_client.table('chatroommembers').insert({'roomid': room_id, 'userid': creator.data[0]['userid']}).execute()
    flash('Tạo phòng thành công!', 'success')
    return redirect(url_for('chat'))

# Endpoint xử lý gửi tin nhắn nhóm qua AJAX
@app.route('/group_chat/send/<int:roomid>', methods=['POST'])
def send_group_message(roomid):
    print(f"Received message request for room {roomid}")
    print(f"Form data: {request.form}")
    print(f"Session data: {session}")

    if 'user' not in session:
        print("User not logged in")
        return {"error": "Vui lòng đăng nhập lại"}, 401
        
    try:
        print(f"Processing message from user {session['user']}")
        # Lấy thông tin người gửi
        my_res = supabase_client.table('users').select('userid, username').eq('username', session['user']).execute()
        if not my_res.data:
            print("User not found in database")
            return {"error": "User not found"}, 400
            
        my_id = my_res.data[0]['userid']
        my_username = my_res.data[0]['username']
        print(f"Found user: {my_username} (ID: {my_id})")
            
        # Kiểm tra xem người dùng có trong phòng không
        member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', roomid).eq('userid', my_id).execute()
        if not member_check.data:
            print(f"User {my_username} is not a member of room {roomid}")
            return {"error": "Not a member of this room"}, 403
            
        content = request.form.get('content', '').strip()
        print(f"Message content: {content}")
        if not content:
            print("Empty message received")
            return {"error": "Empty message"}, 400
            
        # Lưu tin nhắn vào CSDL
        message_data = {
            'userid': my_id,
            'roomid': roomid,
            'content': content,
            'createdat': datetime.now().isoformat()
        }
        print(f"Saving message data: {message_data}")
        
        res = supabase_client.table('chatroommessages').insert(message_data).execute()
        print(f"Supabase response: {res.data}")
        
        if res.data:
            # Trả về tin nhắn với username để hiển thị ngay
            response_data = {
                "success": True,
                "message": {
                    **res.data[0],
                    'username': my_username,
                    'userid': my_id
                }
            }
            print(f"Sending success response: {response_data}")
            return response_data, 200
            
        print("Failed to save message - no data returned")
        return {"error": "Failed to save message"}, 500
        
    except Exception as e:
        print(f"Error in send_group_message: {str(e)}")
        return {"error": f"Server error: {str(e)}"}, 500

# Endpoint trả về tin nhắn nhóm dưới dạng JSON cho AJAX polling
@app.route('/group_chat/messages/<int:roomid>')
def get_group_messages(roomid):
    if 'user' not in session:
        return {"error": "Not logged in"}, 401
        
    try:
        # Lấy thông tin người dùng
        my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        my_id = my_res.data[0]['userid'] if my_res.data else None
        if not my_id:
            return {"error": "User not found"}, 400
            
        # Kiểm tra xem người dùng có trong phòng không
        member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', roomid).eq('userid', my_id).execute()
        if not member_check.data:
            return {"error": "Not a member of this room"}, 403
            
        # Lấy tin nhắn mới nhất nếu có ID tin nhắn cuối
        after_id = request.args.get('after', '0')
        msg_res = supabase_client.table('chatroommessages').select('*').eq('roomid', roomid).gt('messageid', after_id).order('createdat', desc=False).limit(50).execute()
        
        messages = []
        if msg_res.data:
            # Lấy danh sách user ID từ tin nhắn
            user_ids = list(set(msg['userid'] for msg in msg_res.data))
            # Lấy thông tin người dùng
            users_res = supabase_client.table('users').select('userid, username').in_('userid', user_ids).execute()
            users = {user['userid']: user['username'] for user in (users_res.data or [])}
            
            # Kết hợp thông tin tin nhắn với tên người gửi và userid
            messages = [{
                **msg,
                'userid': msg['userid'],  # Đảm bảo userid được bao gồm
                'username': users.get(msg['userid'], 'Unknown User')
            } for msg in msg_res.data]
            
        return {"messages": messages}, 200
        
    except Exception as e:
        return {"error": str(e)}, 500

# Route xem phòng chat cụ thể
@app.route('/group_chat/<int:roomid>')
def group_chat(roomid):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    # Lấy thông tin người dùng
    my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    my_id = my_res.data[0]['userid'] if my_res.data else None
    if not my_id:
        flash('Không tìm thấy thông tin người dùng!', 'error')
        return redirect(url_for('chat'))
        
    # Kiểm tra xem phòng có tồn tại không
    room_res = supabase_client.table('chatrooms').select('*').eq('roomid', roomid).execute()
    if not room_res.data:
        flash('Không tìm thấy phòng chat!', 'error')
        return redirect(url_for('chat'))
    room = room_res.data[0]
    
    # Kiểm tra xem người dùng có trong phòng không
    member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', roomid).eq('userid', my_id).execute()
    if not member_check.data:
        flash('Bạn không phải thành viên của phòng chat này!', 'error')
        return redirect(url_for('chat'))
    
    # Lấy tin nhắn trong phòng
    messages = []
    msg_res = supabase_client.table('chatroommessages').select('*').eq('roomid', roomid).order('createdat', desc=False).limit(50).execute()
    
    if msg_res.data:
        # Lấy danh sách user ID từ tin nhắn
        user_ids = list(set(msg['userid'] for msg in msg_res.data))
        # Lấy thông tin người dùng
        users_res = supabase_client.table('users').select('userid, username').in_('userid', user_ids).execute()
        users = {user['userid']: user['username'] for user in (users_res.data or [])}
        
        # Kết hợp thông tin tin nhắn với tên người gửi
        messages = [{
            **msg,
            'username': users.get(msg['userid'], 'Unknown User')
        } for msg in msg_res.data]
    
    return render_template('group_chat.html', room=room, messages=messages, my_id=my_id)

# Route: Chat page (list rooms, chat room, chat private)
@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect(url_for('login'))
    rooms = []
    recent_chats = []

    # Lấy ID người dùng hiện tại
    my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    my_id = my_res.data[0]['userid'] if my_res.data else None

    # Lấy danh sách phòng chat mà người dùng là thành viên
    if my_id:
        # Lấy danh sách ID phòng chat mà người dùng là thành viên
        members_res = supabase_client.table('chatroommembers').select('roomid').eq('userid', my_id).execute()
        room_ids = [member['roomid'] for member in (members_res.data or [])]
        
        # Lấy thông tin các phòng chat từ danh sách ID
        if room_ids:
            rooms_res = supabase_client.table('chatrooms').select('*').in_('roomid', room_ids).execute()
            rooms = rooms_res.data if rooms_res.data else []
        
        # Lấy danh sách users đã từng chat (có tin nhắn)
        # Lấy tin nhắn mà mình gửi đi
        sent_msgs = supabase_client.table('privatemessages').select('receiverid, content, createdat').eq('senderid', my_id).order('createdat', desc=True).execute()
        # Lấy tin nhắn mà mình nhận được
        received_msgs = supabase_client.table('privatemessages').select('senderid, content, createdat').eq('receiverid', my_id).order('createdat', desc=True).execute()
        
        # Tạo dict để track user và tin nhắn cuối
        user_messages = {}
        
        # Xử lý tin nhắn gửi đi
        if sent_msgs.data:
            for msg in sent_msgs.data:
                uid = msg['receiverid']
                if uid not in user_messages:
                    user_messages[uid] = {
                        'last_message': msg.get('content', ''),
                        'last_time': msg.get('createdat', '')
                    }
        
        # Xử lý tin nhắn nhận được
        if received_msgs.data:
            for msg in received_msgs.data:
                uid = msg['senderid']
                if uid not in user_messages:
                    user_messages[uid] = {
                        'last_message': msg.get('content', ''),
                        'last_time': msg.get('createdat', '')
                    }
                # Cập nhật nếu tin nhắn này mới hơn
                elif msg.get('createdat', '') > user_messages[uid]['last_time']:
                    user_messages[uid]['last_message'] = msg.get('content', '')
                    user_messages[uid]['last_time'] = msg.get('createdat', '')
        
        # Lấy thông tin user từ user_ids
        if user_messages:
            user_ids = list(user_messages.keys())
            users_res = supabase_client.table('users').select('userid, username').in_('userid', user_ids).execute()
            if users_res.data:
                recent_chats = [{
                    'userid': user['userid'],
                    'username': user['username'],
                    'last_message': user_messages[user['userid']]['last_message']
                } for user in users_res.data]

    return render_template('chat.html', rooms=rooms, recent_chats=recent_chats)

# Route tìm kiếm users
@app.route('/search_users')
def search_users():
    if 'user' not in session:
        return {"error": "Not logged in"}, 401
    
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return {"users": []}, 200
    
    try:
        # Tìm users có username chứa query (không phân biệt hoa thường)
        users_res = supabase_client.table('users').select('userid, username').ilike('username', f'%{query}%').neq('username', session['user']).limit(10).execute()
        
        users = users_res.data if users_res.data else []
        return {"users": users}, 200
    except Exception as e:
        return {"error": str(e)}, 500

# Route lấy userid của user hiện tại
@app.route('/get_my_userid')
def get_my_userid():
    if 'user' not in session:
        return {"error": "Not logged in"}, 401
    
    my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    my_id = my_res.data[0]['userid'] if my_res.data else None
    
    if my_id:
        return {"userid": my_id}, 200
    else:
        return {"error": "User not found"}, 404

# Route xóa tin nhắn nhóm
@app.route('/delete_group_messages/<int:roomid>', methods=['POST'])
def delete_group_messages(roomid):
    if 'user' not in session:
        return {"error": "Not logged in"}, 401
    
    try:
        # Lấy thông tin người dùng
        my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        my_id = my_res.data[0]['userid'] if my_res.data else None
        if not my_id:
            return {"error": "User not found"}, 400
        
        # Kiểm tra xem người dùng có trong phòng không
        member_check = supabase_client.table('chatroommembers').select('*').eq('roomid', roomid).eq('userid', my_id).execute()
        if not member_check.data:
            return {"error": "Not a member of this room"}, 403
        
        # Xóa tất cả tin nhắn trong phòng
        supabase_client.table('chatroommessages').delete().eq('roomid', roomid).execute()
        
        return {"success": True, "message": "Đã xóa tất cả tin nhắn"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

# Route xóa tin nhắn riêng
@app.route('/delete_private_messages/<int:userid>', methods=['POST'])
def delete_private_messages(userid):
    if 'user' not in session:
        return {"error": "Not logged in"}, 401
    
    try:
        # Lấy ID người dùng hiện tại
        my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        my_id = my_res.data[0]['userid'] if my_res.data else None
        if not my_id:
            return {"error": "User not found"}, 400
        
        # Xóa tin nhắn giữa 2 user (cả 2 chiều)
        # Xóa tin nhắn từ mình gửi cho user kia
        supabase_client.table('privatemessages').delete().eq('senderid', my_id).eq('receiverid', userid).execute()
        # Xóa tin nhắn từ user kia gửi cho mình
        supabase_client.table('privatemessages').delete().eq('senderid', userid).eq('receiverid', my_id).execute()
        
        return {"success": True, "message": "Đã xóa tất cả tin nhắn riêng"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

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
    import base64
    
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

# Endpoint trả về tin nhắn riêng dưới dạng JSON cho AJAX polling
@app.route('/private_chat/messages/<int:userid>')
def get_private_messages(userid):
    if 'user' not in session:
        return {"error": "Not logged in"}, 401
    my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
    my_id = my_res.data[0]['userid'] if my_res.data else None
    if not my_id:
        return {"error": "Missing user id"}, 400
    logic = f"and(senderid.eq.{my_id},receiverid.eq.{userid}),and(senderid.eq.{userid},receiverid.eq.{my_id})"
    msg_res = supabase_client.table('privatemessages').select('*').or_(logic).order('createdat', desc=False).limit(50).execute()
    messages = []
    if msg_res.data:
        for msg in msg_res.data:
            msg['messageid'] = msg.get('messageid') or msg.get('MessageID')  # Handle both column names
            messages.append(msg)
    return {"messages": messages}, 200

# Endpoint xử lý gửi tin nhắn riêng qua AJAX
@app.route('/private_chat/send/<int:userid>', methods=['POST'])
def send_private_message(userid):
    if 'user' not in session:
        return {"error": "Not logged in"}, 401
    try:
        my_res = supabase_client.table('users').select('userid').eq('username', session['user']).execute()
        my_id = my_res.data[0]['userid'] if my_res.data else None
        if not my_id:
            return {"error": "Missing user id"}, 400
            
        content = request.form.get('content', '').strip()
        if not content:
            return {"error": "Empty message"}, 400
            
        res = supabase_client.table('privatemessages').insert({
            'senderid': my_id,
            'receiverid': userid,
            'content': content,
            'createdat': datetime.now().isoformat()
        }).execute()
        
        if res.data:
            return {"success": True, "message": res.data[0]}, 200
        return {"error": "Failed to save message"}, 500
        
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    # Chạy server trên port 5000 và cho phép truy cập từ mọi IP
    app.run(host='0.0.0.0', port=5000, debug=True)