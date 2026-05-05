#!/usr/bin/env python3
"""
Lightweight Replit-compatible app - minimal HTML without heavy DB queries
"""
from flask import Flask, render_template_string
import os
import sys

app = Flask(__name__)

# HTML Template
HTML = """
<!DOCTYPE html>
<html lang="zh-HK">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>港股通持股變動分析</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { margin-top: 100px; }
        .card { box-shadow: 0 10px 30px rgba(0,0,0,0.3); border: none; }
        .btn-primary { background: linear-gradient(90deg, #667eea, #764ba2); border: none; }
        .btn-primary:hover { transform: translateY(-2px); }
    </style>
</head>
<body>
    <div class="container text-center text-white">
        <h1 class="mb-4">🎉 應用已成功上線！</h1>
        
        <div class="card text-dark" style="max-width: 500px; margin: 0 auto;">
            <div class="card-body p-5">
                <h3 class="card-title mb-4">港股通持股變動分析</h3>
                
                <p class="lead text-success mb-4">✅ 應用運行正常</p>
                
                <div class="alert alert-info">
                    <strong>首次加載提示：</strong><br>
                    應用正在初始化數據庫連接...<br>
                    <small>（首次訪問需要 30-60 秒）</small>
                </div>
                
                <button class="btn btn-primary btn-lg w-100" onclick="loadApp()">
                    進入應用 →
                </button>
                
                <hr class="my-4">
                
                <p class="small text-muted">
                    版本 1.0 | Replit 部署<br>
                    <a href="https://github.com/wmsing/cn_water" class="link-primary">GitHub 代碼庫</a>
                </p>
            </div>
        </div>
        
        <p class="mt-5 text-light">
            🚀 享受您的股票分析！
        </p>
    </div>

    <script>
        function loadApp() {
            const btn = event.target;
            btn.disabled = true;
            btn.innerHTML = '⏳ 加載中...';
            
            // 嘗試調用完整應用的 API 以觸發初始化
            fetch('/api/health')
                .then(r => r.json())
                .then(data => {
                    window.location.href = '/dashboard';
                })
                .catch(err => {
                    btn.innerHTML = '重試';
                    btn.disabled = false;
                    alert('加載失敗，請重試');
                });
        }

        // 自動重定向到完整應用（5秒後）
        setTimeout(() => {
            if (document.body.innerHTML.includes('進入應用')) {
                console.log('自動轉向完整應用...');
                window.location.href = '/dashboard';
            }
        }, 5000);
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def landing():
    """簡單的著陸頁面"""
    return render_template_string(HTML)

@app.route('/api/health', methods=['GET'])
def health():
    """健康檢查 - 用於激發應用初始化"""
    try:
        from app import app as full_app
        return {'status': 'ready'}, 200
    except Exception as e:
        return {'status': 'loading', 'error': str(e)}, 202

@app.route('/dashboard', methods=['GET'])
def dashboard_redirect():
    """重定向到完整應用"""
    try:
        from app import index
        return index()
    except Exception as e:
        return f"""
        <html><body style="font-family: Arial; padding: 50px;">
            <h1>❌ 應用加載失敗</h1>
            <p>錯誤: {str(e)}</p>
            <p><a href="/">返回首頁</a></p>
        </body></html>
        """, 500

if __name__ == '__main__':
    os.makedirs("templates", exist_ok=True)
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    
    print(f"🚀 輕量級應用啟動...", file=sys.stderr)
    print(f"   Host: {host}", file=sys.stderr)
    print(f"   Port: {port}", file=sys.stderr)
    
    app.run(debug=False, host=host, port=port, use_reloader=False)
