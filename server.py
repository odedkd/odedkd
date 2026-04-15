#!/usr/bin/env python3
"""
Claude Code UI — Multi-Bot Web Interface (v19.8)
Flask server for Claude Code, HafakR104, and queue management
"""

from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import uuid
import subprocess
import threading
import time
import requests
from datetime import datetime
from functools import wraps
import io

app = Flask(__name__, template_folder='templates', static_folder='static')

# Configuration
QUEUE_FILE = '/tmp/claude_code_queue.json'
UPLOADS_DIR = '/tmp/cc_uploads/'
RESULTS_DIR = 'results/'
LOGS_DIR = 'logs/'
MAX_QUEUE_SIZE = 50
CLAUDE_CODE_TIMEOUT = 300  # 5 minutes
HAFAK_TIMEOUT = 60  # 1 minute

# Ensure directories exist
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# IP allowlist (Tailscale + localhost)
def require_tailscale(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = request.remote_addr
        if not (ip in ('127.0.0.1', '::1') or ip.startswith('100.')):
            return jsonify({'error': 'Access denied'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Task queue management
def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, 'r') as f:
            return json.load(f)
    return []

def save_queue(queue):
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=2)

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
def process_claude_code_task(task_id):
    queue = load_queue()
    task = next((t for t in queue if t['id'] == task_id), None)

    if not task:
        return

    task['status'] = 'running'
    task['started_at'] = datetime.now().isoformat()
    save_queue(queue)

    try:
        # Simulate Claude Code execution (in real scenario, use subprocess to call claude CLI)
        result = f"Processed: {task['prompt'][:100]}..."

        task['status'] = 'done'
        task['result'] = result
        task['completed_at'] = datetime.now().isoformat()
    except Exception as e:
        task['status'] = 'error'
        task['error'] = str(e)
        task['completed_at'] = datetime.now().isoformat()

    save_queue(queue)

def process_hafak_task(task_id):
    queue = load_queue()
    task = next((t for t in queue if t['id'] == task_id), None)

    if not task:
        return

    task['status'] = 'running'
    task['started_at'] = datetime.now().isoformat()
    save_queue(queue)

    try:
        # Simulate HafakR104 response
        result = f"HafakR104 response: {task['prompt'][:100]}..."

        task['status'] = 'done'
        task['result'] = result
        task['completed_at'] = datetime.now().isoformat()
    except Exception as e:
        task['status'] = 'error'
        task['error'] = str(e)
        task['completed_at'] = datetime.now().isoformat()

    save_queue(queue)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002, threaded=True)
