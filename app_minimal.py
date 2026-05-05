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
    """Load the full app"""
    try:
        from app import index
        return index()
    except Exception as e:
        return f"<p>加載失敗: {str(e)}</p>", 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    print(f"Starting app_minimal on {host}:{port}", file=sys.stderr, flush=True)
    print(f"Flask app object: {app}", file=sys.stderr, flush=True)
    app.run(debug=False, host=host, port=port, use_reloader=False, threaded=True)
