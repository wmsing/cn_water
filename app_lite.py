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
                
                <button class="btn btn-primary btn-lg w-100" onclick="loadFullApp()">
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
        function loadFullApp() {
            const btn = event.target;
            btn.disabled = true;
            btn.innerHTML = '⏳ 加載中...';
            
            // 初始化完整應用
            fetch('/api/init-full-app', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    // 等待 1 秒後跳轉
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1000);
                })
                .catch(err => {
                    console.error('初始化失敗:', err);
                    btn.innerHTML = '重試';
                    btn.disabled = false;
                });
        }

        // 自動在 10 秒後進入完整應用（如果未點擊按鈕）
        setTimeout(() => {
            if (document.body.innerHTML.includes('進入應用')) {
                console.log('自動轉向完整應用...');
                fetch('/api/init-full-app', { method: 'POST' }).catch(() => {});
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 2000);
            }
        }, 10000);
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
    """簡單的健康檢查"""
    return {
        'status': 'ok',
        'version': '1.0',
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }, 200

@app.route('/api/init-full-app', methods=['POST'])
def init_full_app():
    """
    在後台初始化完整應用（可以考慮在後台執行）
    """
    try:
        # 簡單測試數據庫連接
        import sqlite3
        conn = sqlite3.connect('hkex_southbound.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM shareholding LIMIT 1")
        count = cursor.fetchone()
        conn.close()
        return {
            'status': 'database_ready',
            'records': count[0] if count else 0
        }, 200
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }, 500

@app.route('/dashboard', methods=['GET'])
def dashboard_redirect():
    """重定向到完整應用"""
    return """
    <!DOCTYPE html>
    <html lang="zh-HK">
    <head>
        <meta charset="UTF-8">
        <title>加載應用...</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 100px; background: #f0f0f0; }
            .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #667eea; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        </style>
        <script>
            // 嘗試在後台加載完整應用
            fetch('/api/init-full-app', { method: 'POST' }).catch(() => {});
            
            // 等待 3 秒後重試
            setTimeout(() => {
                // 嘗試加載 Flask 的 /index 路由（完整應用）
                window.location.href = '/index';
            }, 3000);
        </script>
    </head>
    <body>
        <h2>🔄 應用初始化中...</h2>
        <div class="spinner"></div>
        <p>請稍候...</p>
    </body>
    </html>
    """, 200

@app.route('/index', methods=['GET'])
def full_app_index():
    """
    試圖加載完整應用的主路由
    如果失敗，返回友好的錯誤頁面
    """
    try:
        # 動態導入以延遲加載
        import importlib.util
        spec = importlib.util.spec_from_file_location("app", "app.py")
        app_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app_module)
        
        # 呼叫完整應用的 index() 函數
        return app_module.index()
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        return f"""
        <html><body style="font-family: Arial; padding: 50px;">
            <h1>❌ 應用加載失敗</h1>
            <p style="color: red;">{str(e)}</p>
            <hr>
            <pre style="background: #f0f0f0; padding: 10px; overflow: auto; max-height: 300px;">
{error_msg}
            </pre>
            <p><a href="/">← 返回首頁重試</a></p>
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
