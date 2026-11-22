"""Ecosystem Runner: Starts FastAPI Backend, Telegram Bot, and Cloudflare Tunnel."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

# Load .env
ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

PYTHON = sys.executable

backend_log = open(LOGS / "backend.log", "w", encoding="utf-8")
bot_log = open(LOGS / "bot.log", "w", encoding="utf-8")
tunnel_log_file = open(LOGS / "tunnel.log", "w", encoding="utf-8")

print("1. Starting FastAPI Backend Server on port 8000...")
backend_proc = subprocess.Popen(
    [PYTHON, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
    cwd=str(ROOT),
    stdout=backend_log,
    stderr=subprocess.STDOUT,
)

time.sleep(3)

print("2. Starting Telegram Bot (@zeptokarobot)...")
bot_proc = subprocess.Popen(
    [PYTHON, "telegram_bot/main.py"],
    cwd=str(ROOT),
    stdout=bot_log,
    stderr=subprocess.STDOUT,
)

print("3. Starting Cloudflare Quick Tunnel for Web App...")
tunnel_proc = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", "http://127.0.0.1:8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

tunnel_url = None
start_wait = time.time()
url_file = ROOT / "tunnel_url.txt"

# Read cloudflared output to grab trycloudflare.com URL
while time.time() - start_wait < 30:
    line = tunnel_proc.stdout.readline()
    if not line:
        time.sleep(0.5)
        continue
    tunnel_log_file.write(line)
    tunnel_log_file.flush()
    match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
    if match:
        tunnel_url = match.group(0)
        break

if tunnel_url:
    print(f"\n==========================================")
    print(f"🚀 LIVE DEPLOYED URL: {tunnel_url}")
    print(f"🤖 TELEGRAM BOT ACTIVE: https://t.me/zeptokarobot")
    print(f"==========================================\n")
    url_file.write_text(tunnel_url, encoding="utf-8")
else:
    print("Cloudflare tunnel started (check logs/tunnel.log)")

# Forward remaining tunnel logs in background thread
import threading
def pipe_tunnel():
    for line in iter(tunnel_proc.stdout.readline, ''):
        tunnel_log_file.write(line)
        tunnel_log_file.flush()
t = threading.Thread(target=pipe_tunnel, daemon=True)
t.start()

# Keep alive
try:
    while True:
        time.sleep(1)
        if backend_proc.poll() is not None:
            print("Backend process exited!")
            break
        if bot_proc.poll() is not None:
            print("Telegram bot process exited!")
            break
except KeyboardInterrupt:
    print("Shutting down ecosystem...")
    backend_proc.terminate()
    bot_proc.terminate()
    tunnel_proc.terminate()
