#!/usr/bin/env python3
"""
Minimal Replit-compatible landing page
No complex imports, no database queries, just static HTML
"""
from flask import Flask
import os
import sys

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    """Static landing page"""
    return """
<!DOCTYPE html>
<html lang="zh-HK">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>港股通持股變動分析</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .card { 
            box-shadow: 0 10px 30px rgba(0,0,0,0.3); 
            border: none;
            border-radius: 15px;
        }
        .btn-primary { 
            background: linear-gradient(90deg, #667eea, #764ba2); 
            border: none;
            padding: 12px 30px;
            font-size: 16px;
        }
        .btn-primary:hover { 
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card" style="max-width: 500px; margin: 0 auto;">
            <div class="card-body p-5 text-center">
                <h1 class="mb-4">🎉</h1>
                <h3 class="card-title mb-4">港股通持股變動分析</h3>
                
                <p class="lead text-success mb-4">✅ 應用已上線</p>
                
                <div class="alert alert-info small">
                    <strong>首次訪問提示：</strong><br>
                    應用正在加載數據庫...<br>
                    （需要 30-60 秒）
                </div>
                
                <button class="btn btn-primary btn-lg w-100" onclick="enterApp()">
                    進入應用 →
                </button>
                
                <hr class="my-4">
                <p class="small text-muted">v1.0 | <a href="https://github.com/wmsing/cn_water">GitHub</a></p>
            </div>
        </div>
    </div>

    <script>
        function enterApp() {
            const btn = event.target;
            btn.disabled = true;
            btn.innerHTML = '⏳ 加載中...';
            window.location.href = '/app';
        }
        
        // 自動重定向（10秒後）
        setTimeout(() => {
            window.location.href = '/app';
        }, 10000);
    </script>
</body>
</html>
    """, 200

@app.route('/app', methods=['GET'])
def serve_app():
    """Try to load the full app"""
    try:
        # Import at request time to avoid startup delays
        from app import index as full_index
        return full_index()
    except ImportError as e:
        return f"""
        <html><body style="font-family: Arial; padding: 40px; background: #f8d7da; border: 1px solid #f5c6cb; margin: 20px; border-radius: 5px;">
            <h2>⚠️ 應用初始化中</h2>
            <p>完整應用正在加載，請稍候...</p>
            <p><small>{str(e)}</small></p>
            <p><a href="/">← 返回首頁</a></p>
        </body></html>
        """, 202
    except Exception as e:
        import traceback
        return f"""
        <html><body style="font-family: Arial; padding: 40px;">
            <h2>❌ 錯誤</h2>
            <p>{str(e)}</p>
            <hr>
            <pre style="background: #f0f0f0; padding: 10px; overflow: auto; max-height: 200px; font-size: 12px;">
{traceback.format_exc()}
            </pre>
            <p><a href="/">← 返回首頁</a></p>
        </body></html>
        """, 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return {'status': 'ok'}, 200

if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    
    print(f"🚀 Starting light app on {host}:{port}", file=sys.stderr, flush=True)
    app.run(debug=False, host=host, port=port, use_reloader=False, threaded=True)
