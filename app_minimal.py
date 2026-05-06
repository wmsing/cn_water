#!/usr/bin/env python3
"""Minimal Flask app wrapper that imports and uses the main app from app.py"""
import sys
import os

# Import the Flask app from app.py
try:
    from app import app
except ImportError as e:
    print(f"ERROR: Could not import app from app.py: {e}", file=sys.stderr, flush=True)
    # Fallback: create a minimal app that shows loading
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/', methods=['GET'])
    def home():
        return """<html><body style="display:flex; align-items:center; justify-content:center; min-height:100vh;">
        <div style="text-align:center; font-family:Arial;"><h2>⚠️ 數據加載中</h2>
        <p>應用正在初始化數據庫...<br><a href="/">← 返回首頁</a></p></div>
        </body></html>""", 202

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    print(f"Starting app on {host}:{port}", file=sys.stderr, flush=True)
    app.run(debug=False, host=host, port=port, use_reloader=False, threaded=True)
