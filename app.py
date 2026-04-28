import os
import json
import secrets
import random
import string
from flask import Flask, render_template, request, jsonify, session, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

# 生成随机secret_key用于session
app.secret_key = secrets.token_hex(32)

# 配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'view_stats.json')
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'webm'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB限制

# 管理员密码（仅在后端使用，不暴露）
ADMIN_PASSWORD = "SEAGULL7"

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def is_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


def get_file_type(filename):
    """获取文件类型：image 或 video"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return 'image'
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        return 'video'
    return None


def generate_password():
    """生成8位随机密码（大写字母+数字）"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def get_image_path(password):
    """获取图片路径"""
    return os.path.join(UPLOAD_FOLDER, f"{password}.jpg")


def password_exists(password):
    """验证密码是否存在（对应图片是否存在）"""
    # 检查常见图片格式
    for ext in ALLOWED_EXTENSIONS:
        path = os.path.join(UPLOAD_FOLDER, f"{password}.{ext}")
        if os.path.exists(path):
            return path
    return None


def load_view_stats():
    """加载查看次数统计"""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_view_stats(stats):
    """保存查看次数统计"""
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f)


def increment_view_count(password):
    """增加查看次数"""
    password = password.upper()
    stats = load_view_stats()
    stats[password] = stats.get(password, 0) + 1
    save_view_stats(stats)


def get_view_count(password):
    """获取查看次数"""
    password = password.upper()
    stats = load_view_stats()
    return stats.get(password, 0)


@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/upload-page')
def upload_page():
    """上传页面（需要管理员权限）"""
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    return render_template('upload.html')


@app.route('/api/check-password', methods=['POST'])
def check_password():
    """验证密码是否存在"""
    data = request.json
    password = data.get('password', '').strip().upper()

    if not password:
        return jsonify({'exists': False})

    file_path = password_exists(password)
    if file_path:
        ext = os.path.splitext(file_path)[1][1:]
        file_type = 'video' if ext in ALLOWED_VIDEO_EXTENSIONS else 'image'
        return jsonify({'exists': True, 'extension': ext, 'type': file_type})
    return jsonify({'exists': False})


@app.route('/image/<password>')
def get_image(password):
    """获取图片文件"""
    password = password.upper()
    image_path = password_exists(password)

    if not image_path:
        return "图片不存在", 404

    return send_from_directory(app.config['UPLOAD_FOLDER'], os.path.basename(image_path))


@app.route('/file/<password>')
def get_file(password):
    """获取文件（图片或视频）- 增加查看计数"""
    password = password.upper()
    file_path = password_exists(password)

    if not file_path:
        return "文件不存在", 404

    increment_view_count(password)

    from flask import make_response
    import mimetypes

    filename = os.path.basename(file_path)
    mime_type, _ = mimetypes.guess_type(filename)

    response = make_response(send_from_directory(app.config['UPLOAD_FOLDER'], filename))
    response.headers['Content-Type'] = mime_type or 'application/octet-stream'
    return response


@app.route('/preview/<password>')
def preview_file(password):
    """预览文件（图片或视频）- 不增加查看计数"""
    password = password.upper()
    file_path = password_exists(password)

    if not file_path:
        return "文件不存在", 404

    from flask import make_response
    import mimetypes

    filename = os.path.basename(file_path)
    mime_type, _ = mimetypes.guess_type(filename)

    response = make_response(send_from_directory(app.config['UPLOAD_FOLDER'], filename))
    response.headers['Content-Type'] = mime_type or 'application/octet-stream'
    return response


@app.route('/login', methods=['POST'])
def login():
    """管理员登录"""
    data = request.json
    password = data.get('password', '').strip()

    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({'success': True})

    return jsonify({'success': False}), 401


@app.route('/logout', methods=['POST'])
def logout():
    """管理员登出"""
    session.pop('is_admin', None)
    return jsonify({'success': True})


@app.route('/upload', methods=['POST'])
def upload():
    """上传图片或视频（需要管理员权限）"""
    if not session.get('is_admin'):
        return jsonify({'success': False, 'message': '需要管理员权限'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': '不支持的文件类型'}), 400

    # 生成唯一密码
    password = generate_password()
    while password_exists(password):
        password = generate_password()

    # 获取文件扩展名并保存
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{password}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    file_type = get_file_type(file.filename)

    return jsonify({
        'success': True,
        'password': password,
        'file_type': file_type,
        'url': url_for('get_file', password=password, _external=True)
    })


@app.route('/delete/<password>', methods=['POST'])
def delete_image(password):
    """删除图片（需要管理员权限）"""
    if not session.get('is_admin'):
        return jsonify({'success': False, 'message': '需要管理员权限'}), 401

    password = password.upper()
    image_path = password_exists(password)

    if not image_path:
        return jsonify({'success': False, 'message': '图片不存在'}), 404

    try:
        os.remove(image_path)
        # 删除查看次数统计
        stats = load_view_stats()
        if password in stats:
            del stats[password]
            save_view_stats(stats)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/images', methods=['GET'])
def list_images():
    """获取文件列表（图片和视频，需要管理员权限）"""
    if not session.get('is_admin'):
        return jsonify({'success': False, 'message': '需要管理员权限'}), 401

    stats = load_view_stats()
    images = []
    if os.path.exists(UPLOAD_FOLDER):
        for filename in os.listdir(UPLOAD_FOLDER):
            # 检查所有允许的扩展名
            for ext in ALLOWED_EXTENSIONS:
                if filename.endswith(f'.{ext}'):
                    password = filename[:-len(ext)-1]  # 去掉扩展名
                    file_type = 'video' if ext in ALLOWED_VIDEO_EXTENSIONS else 'image'
                    images.append({
                        'filename': filename,
                        'password': password,
                        'type': file_type,
                        'url': url_for('preview_file', password=password, _external=True),
                        'view_count': stats.get(password, 0)
                    })
                    break

    return jsonify({'success': True, 'images': images})


@app.route('/admin')
def admin_page():
    """管理员控制台页面"""
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    return render_template('admin.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
