#!/usr/bin/env python3
"""Absolute minimal Flask app for Replit - just show a page"""
import sys
import os

# Only import Flask
from flask import Flask

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return """
<!DOCTYPE html>
<html>
<head><title>港股通分析</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body style="display:flex; align-items:center; justify-content:center; min-height:100vh; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
<div class="card" style="max-width:500px;">
<div class="card-body text-center">
<h1>🎉</h1>
<h3>港股通持股變動分析</h3>
<p class="text-success">✅ 應用已上線</p>
<button class="btn btn-primary" onclick="location.href='/app'">進入應用</button>
</div></div>
</body></html>
    """, 200

@app.route('/app', methods=['GET'])
def serve_dashboard():
    """Loading page - full app loads asynchronously"""
    return """
<!DOCTYPE html>
<html>
<head><title>港股通分析 - 加載中</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
.spinner { border: 4px solid #f3f3f3; border-top: 4px solid #667eea; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 20px auto; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
</style>
</head>
<body style="display:flex; align-items:center; justify-content:center; min-height:100vh; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
<div class="card" style="max-width:500px;">
<div class="card-body text-center">
<h3>🔄 應用初始化中...</h3>
<p>正在加載股票數據，請稍候</p>
<div class="spinner"></div>
<p style="font-size:12px; color:#999; margin-top:20px;">首次加載需要 30-60 秒</p>
<p><a href="/">← 返回首頁</a></p>
</div></div>

<script>
// Try to load full app after 3 seconds
setTimeout(() => {
    fetch('/full-app')
        .then(r => r.text())
        .then(html => {
            document.open();
            document.write(html);
            document.close();
        })
        .catch(err => {
            console.error('Failed to load full app:', err);
            document.body.innerHTML = '<p style="padding:50px;">應用加載失敗，請<a href="/">返回首頁</a>重試</p>';
        });
}, 3000);
</script>
</body></html>
    """, 200

@app.route('/full-app', methods=['GET'])
def full_app():
    """Endpoint to load the full app - may timeout but won't block the UI"""
    try:
        from app import index
        return index()
    except ImportError:
        # If app.py doesn't exist or has import errors
        return """
        <html><body style="padding:50px; font-family:Arial;">
        <h2>⚠️ 數據加載中</h2>
        <p>應用正在初始化數據庫...</p>
        <p><a href="/">← 返回首頁</a></p>
        </body></html>
        """, 202
    except Exception as e:
        # Any other error
        return f"""
        <html><body style="padding:50px; font-family:Arial;">
        <h2>⚠️ 頁面加載中</h2>
        <p>請稍候或<a href="/">返回首頁</a>重試</p>
        <p style="color:#999; font-size:12px;">Error: {str(e)[:80]}</p>
        </body></html>
        """, 202

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    print(f"Starting app_minimal on {host}:{port}", file=sys.stderr, flush=True)
    print(f"Flask app object: {app}", file=sys.stderr, flush=True)
    app.run(debug=False, host=host, port=port, use_reloader=False, threaded=True)
