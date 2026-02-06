from flask import Flask, render_template, jsonify, request
from flask_compress import Compress
from flask_caching import Cache
import json
import os
import re
import threading
import time
import socket
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='Templates')

# Compression
compress = Compress()
compress.init_app(app)

# Caching
cache_config = {
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 2,
}
app.config.from_mapping(cache_config)
cache = Cache(app)

DATA_FILE = "/app/data/ping_data.json"
DEVICES_FILE = "/app/data/devices.json"
HISTORY_FILE = "/app/data/ping_history.json"
SERVERS_FILE = "/app/data/servers.json"

IP_PATTERN = re.compile(r'^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$')

file_lock = threading.Lock()


def load_json(filepath, default=None):
    """Safely load JSON from a file."""
    if default is None:
        default = {}
    try:
        with open(filepath) as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        logger.warning("Corrupt JSON in %s, returning default", filepath)
        return default
    except Exception as e:
        logger.error("Error reading %s: %s", filepath, e)
        return default


def save_json(filepath, data):
    """Safely write JSON to a file under lock."""
    with file_lock:
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Error writing %s: %s", filepath, e)


def load_devices():
    devices = load_json(DEVICES_FILE)
    if not devices:
        default_devices_str = os.getenv('DEFAULT_DEVICES', '')
        if default_devices_str:
            devices = {}
            for pair in default_devices_str.split(','):
                if ':' in pair:
                    name, ip = pair.split(':', 1)
                    devices[name.strip()] = ip.strip()
            return devices
    return devices


def save_devices(devices):
    save_json(DEVICES_FILE, devices)


def load_history():
    return load_json(HISTORY_FILE)


def save_history(history):
    save_json(HISTORY_FILE, history)


# ── Routes ───────────────────────────────────────────

@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/api/health')
def health():
    """Health check endpoint for Docker / load balancers."""
    return jsonify({"status": "ok", "timestamp": time.time()})


@app.route('/api/data')
@cache.cached(timeout=1)
def get_data():
    try:
        with file_lock:
            with open(DATA_FILE) as f:
                return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"error": "No data available yet", "devices": {}}), 200
    except Exception as e:
        logger.error("Error reading data: %s", e)
        return jsonify({"error": "Internal error"}), 500


@app.route('/api/devices', methods=['GET'])
def get_devices():
    return jsonify(load_devices())


@app.route('/api/devices', methods=['POST'])
def add_device():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    name = (data.get('name') or '').strip()
    ip = (data.get('ip') or '').strip()

    if not name or not ip:
        return jsonify({"status": "error", "message": "Name and IP are required"}), 400

    if len(name) > 64:
        return jsonify({"status": "error", "message": "Name too long (max 64 chars)"}), 400

    if not IP_PATTERN.match(ip):
        return jsonify({"status": "error", "message": "Invalid IP address"}), 400

    devices = load_devices()
    if name in devices:
        return jsonify({"status": "error", "message": "Device already exists"}), 400

    devices[name] = ip
    save_devices(devices)
    logger.info("Device added: %s (%s)", name, ip)
    return jsonify({"status": "success"})


@app.route('/api/devices', methods=['DELETE'])
def delete_device():
    data = request.get_json(silent=True)
    if not data or not data.get('name'):
        return jsonify({"status": "error", "message": "Device name is required"}), 400

    name = data['name'].strip()
    devices = load_devices()

    if name not in devices:
        return jsonify({"status": "error", "message": "Device not found"}), 404

    del devices[name]
    save_devices(devices)

    history = load_history()
    if name in history:
        del history[name]
        save_history(history)

    logger.info("Device deleted: %s", name)
    return jsonify({"status": "success"})


@app.route('/api/history/<device_name>')
def get_device_history(device_name):
    history = load_history()
    return jsonify(history.get(device_name, []))


@app.route('/api/stats')
@cache.cached(timeout=2)
def get_stats():
    try:
        with file_lock:
            with open(DATA_FILE) as f:
                data = json.load(f)

        devices = data.get('devices', {})
        total = len(devices)
        online = sum(1 for d in devices.values() if d.get('reachable'))
        latencies = [d['latency'] for d in devices.values() if d.get('reachable') and d.get('latency')]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        return jsonify({
            "total": total,
            "online": online,
            "offline": total - online,
            "avg_latency": round(avg_latency, 2),
            "timestamp": data.get('timestamp', '')
        })
    except Exception as e:
        logger.error("Error computing stats: %s", e)
        return jsonify({"total": 0, "online": 0, "offline": 0, "avg_latency": 0})


@app.route('/api/config')
@cache.cached(timeout=60)
def get_config():
    return jsonify({
        "ai_server_url": os.getenv('AI_SERVER_URL', ''),
        "logging_server_url": os.getenv('LOGGING_SERVER_URL', ''),
        "webhook_url": os.getenv('WEBHOOK_URL', ''),
        "platform_urls": {
            "monitor": os.getenv('PLATFORM_MONITOR_URL', ''),
            "logs": os.getenv('PLATFORM_LOGS_URL', ''),
            "ai": os.getenv('PLATFORM_AI_URL', '')
        }
    })


# ── Server Management ────────────────────────────────

def load_servers():
    servers = load_json(SERVERS_FILE)
    if not servers:
        # No default servers - users configure their own via the UI or API
        # Example: {"MyServer": {"host": "10.0.0.1", "port": 22, "user": "admin", "description": "Example Server"}}
        return {}
    return servers


def save_servers(servers):
    save_json(SERVERS_FILE, servers)


def check_ssh_port(host, port, timeout=2):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_ping(host, timeout=1):
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), host],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


@app.route('/api/servers', methods=['GET'])
def get_servers():
    servers = load_servers()
    status_data = {}
    for name, server in servers.items():
        host = server.get('host', '')
        port = server.get('port', 22)
        ping_status = check_ping(host)
        ssh_status = check_ssh_port(host, port)
        status_data[name] = {
            **server,
            "ping_online": ping_status,
            "ssh_online": ssh_status,
            "status": "online" if ssh_status else ("reachable" if ping_status else "offline"),
            "ssh_command": f"ssh -p {port} {server.get('user', 'root')}@{host}"
        }
    return jsonify(status_data)


@app.route('/api/servers', methods=['POST'])
def add_server():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    required = ['name', 'host', 'port', 'user']
    if not all(data.get(k) for k in required):
        return jsonify({"status": "error", "message": "Missing required fields: name, host, port, user"}), 400

    name = data.pop('name').strip()
    if len(name) > 64:
        return jsonify({"status": "error", "message": "Name too long"}), 400

    servers = load_servers()
    if name in servers:
        return jsonify({"status": "error", "message": "Server already exists"}), 400

    servers[name] = {
        "host": data['host'].strip(),
        "port": int(data['port']),
        "user": data['user'].strip(),
        "description": data.get('description', '').strip()
    }
    save_servers(servers)
    logger.info("Server added: %s", name)
    return jsonify({"status": "success", "message": f"Server {name} added"})


@app.route('/api/servers/<name>', methods=['DELETE'])
def delete_server(name):
    servers = load_servers()
    if name not in servers:
        return jsonify({"status": "error", "message": "Server not found"}), 404
    del servers[name]
    save_servers(servers)
    logger.info("Server deleted: %s", name)
    return jsonify({"status": "success", "message": f"Server {name} deleted"})


@app.route('/api/servers/<name>/check', methods=['GET'])
def check_server_status(name):
    servers = load_servers()
    if name not in servers:
        return jsonify({"error": "Server not found"}), 404
    server = servers[name]
    host = server.get('host', '')
    port = server.get('port', 22)
    ping_status = check_ping(host)
    ssh_status = check_ssh_port(host, port)
    return jsonify({
        "name": name, "host": host, "port": port,
        "ping_online": ping_status, "ssh_online": ssh_status,
        "status": "online" if ssh_status else ("reachable" if ping_status else "offline"),
        "ssh_command": f"ssh -p {port} {server.get('user', 'root')}@{host}",
        "timestamp": time.time()
    })


if __name__ == '__main__':
    os.makedirs('/app/data', exist_ok=True)
    if not os.path.exists(DEVICES_FILE):
        save_devices(load_devices())
    if not os.path.exists(SERVERS_FILE):
        save_servers(load_servers())
    logger.info("Starting RellCloud NetOps API server on :5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
