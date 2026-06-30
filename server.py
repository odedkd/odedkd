#!/usr/bin/env python3
"""
Claude Code UI — Multi-Bot Web Interface (v19.8)
Flask server for Claude Code, HafakR104, and queue management
"""

from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import shutil
import tempfile
import uuid
import ipaddress
import subprocess
import threading
import time
import requests
from datetime import datetime
from functools import wraps
import io

app = Flask(__name__, template_folder='templates', static_folder='static')

# Configuration
_TMP_DIR = tempfile.gettempdir()
QUEUE_FILE = os.path.join(_TMP_DIR, 'claude_code_queue.json')
UPLOADS_DIR = os.path.join(_TMP_DIR, 'cc_uploads')
RESULTS_DIR = 'results/'
LOGS_DIR = 'logs/'
MAX_QUEUE_SIZE = 50
CLAUDE_CODE_TIMEOUT = 300  # 5 minutes
HAFAK_TIMEOUT = 60  # 1 minute

# Local Claude Code agent execution (the "wake an agent" wiring).
# This server runs on the local machine, so it can launch a REAL local Claude
# Code agent in the facility folder. Override any of these via environment vars:
#   CLAUDE_BIN             - path/name of the claude CLI (Windows may need 'claude.cmd' or a full path)
#   CLAUDE_WORKDIR         - directory the agent runs in
#   CLAUDE_PERMISSION_MODE - permission gate for the agent. Defaults to the SAFE
#                            'default' mode (approvals still apply); set it
#                            DELIBERATELY to 'acceptEdits' or 'bypassPermissions'
#                            for unattended work — bypass runs everything with no
#                            approval gate, so only enable it knowingly.
CLAUDE_BIN = os.environ.get('CLAUDE_BIN', 'claude')
CLAUDE_WORKDIR = os.environ.get('CLAUDE_WORKDIR', r'G:\My Drive\ROTHSCHILD_10_CORE')
CLAUDE_PERMISSION_MODE = os.environ.get('CLAUDE_PERMISSION_MODE', 'default')

# Ensure directories exist
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# IP allowlist: loopback + Tailscale only (CGNAT 100.64.0.0/10 and IPv6 ULA fd7a:115c:a1e0::/48).
# A plain '100.' string prefix would wrongly admit public 100.0.0.0/8 addresses, so match the
# real network ranges — this is the only gate in front of /submit, which spawns a real local agent.
TAILSCALE_RANGES = (
    ipaddress.ip_network('100.64.0.0/10'),
    ipaddress.ip_network('fd7a:115c:a1e0::/48'),
)

def _is_allowed_ip(ip):
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.is_loopback or any(addr in net for net in TAILSCALE_RANGES)

def require_tailscale(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not _is_allowed_ip(request.remote_addr):
            return jsonify({'error': 'Access denied'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Task queue management.
# All read-modify-write sequences take _queue_lock; save_queue writes atomically
# (temp file + os.replace) so concurrent readers never observe a half-written file.
_queue_lock = threading.Lock()

def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, 'r') as f:
            return json.load(f)
    return []

def save_queue(queue):
    tmp = QUEUE_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(queue, f, indent=2)
    os.replace(tmp, QUEUE_FILE)

def log_task(task):
    with open(os.path.join(LOGS_DIR, 'tasks.log'), 'a') as f:
        f.write(json.dumps(task) + '\n')

# Routes
@app.route('/')
@require_tailscale
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
@require_tailscale
def health():
    return jsonify({'status': 'ok', 'port': 8002}), 200

@app.route('/queue', methods=['GET'])
@require_tailscale
def get_queue():
    return jsonify(load_queue()), 200

@app.route('/task/<task_id>', methods=['GET'])
@require_tailscale
def get_task(task_id):
    queue = load_queue()
    task = next((t for t in queue if t['id'] == task_id), None)
    if task:
        return jsonify(task), 200
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/settings', methods=['GET'])
@require_tailscale
def api_settings():
    # Return current Claude Code settings
    return jsonify({
        'model': 'claude-sonnet-4-6',
        'thinking': False,
        'effort': 'balanced'
    }), 200

@app.route('/upload', methods=['POST'])
@require_tailscale
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Save uploaded file
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    file.save(filepath)

    return jsonify({'file_id': file_id, 'filename': filename}), 200

@app.route('/submit', methods=['POST'])
@require_tailscale
def submit_task():
    data = request.get_json()
    prompt = data.get('prompt', '')

    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    # Create task
    task_id = str(uuid.uuid4())
    task = {
        'id': task_id,
        'prompt': prompt,
        'status': 'queued',
        'created_at': datetime.now().isoformat(),
        'started_at': None,
        'completed_at': None,
        'result': None,
        'error': None,
        'bot': 'Claude Code'
    }

    with _queue_lock:
        queue = load_queue()
        if len(queue) >= MAX_QUEUE_SIZE:
            return jsonify({'error': 'Queue full'}), 429
        queue.append(task)
        save_queue(queue)
    log_task(task)

    # Process asynchronously
    threading.Thread(target=process_claude_code_task, args=(task_id,)).start()

    return jsonify({'task_id': task_id, 'status': 'queued'}), 202

@app.route('/submit-hafak', methods=['POST'])
@require_tailscale
def submit_hafak():
    data = request.get_json()
    prompt = data.get('prompt', '')

    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    task_id = str(uuid.uuid4())
    task = {
        'id': task_id,
        'prompt': prompt,
        'status': 'queued',
        'created_at': datetime.now().isoformat(),
        'started_at': None,
        'completed_at': None,
        'result': None,
        'error': None,
        'bot': 'HafakR104'
    }

    with _queue_lock:
        queue = load_queue()
        if len(queue) >= MAX_QUEUE_SIZE:
            return jsonify({'error': 'Queue full'}), 429
        queue.append(task)
        save_queue(queue)
    log_task(task)

    threading.Thread(target=process_hafak_task, args=(task_id,)).start()

    return jsonify({'task_id': task_id, 'status': 'queued'}), 202

@app.route('/hard-restart', methods=['POST'])
@require_tailscale
def hard_restart():
    with _queue_lock:
        queue = load_queue()
        cancelled_count = 0
        for task in queue:
            if task['status'] in ('running', 'queued'):
                task['status'] = 'cancelled'
                task['completed_at'] = datetime.now().isoformat()
                cancelled_count += 1
        save_queue(queue)
    return jsonify({'cancelled': cancelled_count}), 200

@app.route('/download/<task_id>', methods=['GET'])
@require_tailscale
def download_result(task_id):
    result_file = os.path.join(RESULTS_DIR, f'{task_id}.txt')
    if not os.path.exists(result_file):
        return jsonify({'error': 'Result not found'}), 404

    return send_file(result_file, as_attachment=True, download_name=f'{task_id}.txt')

# Task processing
def _set_task(task_id, **fields):
    """Atomically reload the queue, patch one task's fields, and save — holding
    _queue_lock so concurrent workers/requests don't clobber each other's updates."""
    with _queue_lock:
        queue = load_queue()
        task = next((t for t in queue if t['id'] == task_id), None)
        if task is None:
            return None
        task.update(fields)
        save_queue(queue)
        return task

def run_local_claude(prompt, workdir=None, timeout=CLAUDE_CODE_TIMEOUT):
    """Wake a REAL local Claude Code agent: run the claude CLI headlessly in
    `workdir` and return its text output. Requires the claude CLI to be
    installed and signed in on this machine (override location via CLAUDE_BIN)."""
    bin_path = shutil.which(CLAUDE_BIN) or CLAUDE_BIN
    cmd = [
        bin_path, '-p', prompt,
        '--permission-mode', CLAUDE_PERMISSION_MODE,
    ]
    # On Windows the claude CLI is a .cmd/.bat shim that CreateProcess can't
    # launch directly (WinError 2) — run it through the shell so it resolves.
    use_shell = (os.name == 'nt')
    proc = subprocess.run(
        cmd, cwd=workdir or CLAUDE_WORKDIR,
        capture_output=True, text=True, timeout=timeout,
        shell=use_shell,
    )
    out = (proc.stdout or '').strip()
    err = (proc.stderr or '').strip()
    if proc.returncode != 0:
        raise RuntimeError(err or out or f'claude exited with code {proc.returncode}')
    return out or err or '(הסוכן רץ אך לא החזיר פלט)'

def process_claude_code_task(task_id):
    task = _set_task(task_id, status='running', started_at=datetime.now().isoformat())
    if task is None:
        return

    try:
        result = run_local_claude(task['prompt'])

        # Persist the result so /download/<task_id> can serve it.
        with open(os.path.join(RESULTS_DIR, f'{task_id}.txt'), 'w', encoding='utf-8') as rf:
            rf.write(result)

        _set_task(task_id, status='done', result=result,
                  completed_at=datetime.now().isoformat())
    except subprocess.TimeoutExpired:
        _set_task(task_id, status='error',
                  error=f'Agent timed out after {CLAUDE_CODE_TIMEOUT}s',
                  completed_at=datetime.now().isoformat())
    except Exception as e:
        _set_task(task_id, status='error', error=str(e),
                  completed_at=datetime.now().isoformat())

def process_hafak_task(task_id):
    task = _set_task(task_id, status='running', started_at=datetime.now().isoformat())
    if task is None:
        return

    try:
        # Simulate HafakR104 response (R104 wiring is future — see CLAUDE.md)
        result = f"HafakR104 response: {task['prompt'][:100]}..."
        _set_task(task_id, status='done', result=result,
                  completed_at=datetime.now().isoformat())
    except Exception as e:
        _set_task(task_id, status='error', error=str(e),
                  completed_at=datetime.now().isoformat())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002, threaded=True)
