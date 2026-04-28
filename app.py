import os
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
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB限制

# 管理员密码（仅在后端使用，不暴露）
ADMIN_PASSWORD = "SEAGULL7"

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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

    image_path = password_exists(password)
    return jsonify({'exists': image_path is not None, 'extension': os.path.splitext(image_path)[1][1:] if image_path else None})


@app.route('/image/<password>')
def get_image(password):
    """获取图片文件"""
    password = password.upper()
    image_path = password_exists(password)

    if not image_path:
        return "图片不存在", 404

    return send_from_directory(app.config['UPLOAD_FOLDER'], os.path.basename(image_path))


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
    """上传图片（需要管理员权限）"""
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

    # 保存文件
    filename = f"{password}.jpg"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    return jsonify({
        'success': True,
        'password': password,
        'image_url': url_for('get_image', password=password, _external=True)
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
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
