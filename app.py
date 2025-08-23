from flask import Flask, render_template, jsonify, request
import json
import os
import threading
import time

app = Flask(__name__, template_folder='Templates', static_folder='static')

DATA_FILE = "/app/data/ping_data.json"
DEVICES_FILE = "/app/data/devices.json"
HISTORY_FILE = "/app/data/ping_history.json"

# Lock for thread-safe file operations
file_lock = threading.Lock()

def load_devices():
    try:
        with open(DEVICES_FILE) as f:
            return json.load(f)
    except:
        return {"PS5": "192.168.4.106", "Router": "192.168.4.1"}

def save_devices(devices):
    with file_lock:
        with open(DEVICES_FILE, 'w') as f:
            json.dump(devices, f, indent=2)

def load_history():
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_history(history):
    with file_lock:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/data')
def get_data():
    try:
        with file_lock:
            with open(DATA_FILE) as f:
                return jsonify(json.load(f))
    except:
        return jsonify({"error": "No data available"})

@app.route('/api/devices', methods=['GET'])
def get_devices():
    try:
        devices = load_devices()
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices', methods=['POST'])
def add_device():
    try:
        devices = load_devices()
        new_device = request.get_json()
        
        # Validate input
        if not new_device.get('name') or not new_device.get('ip'):
            return jsonify({"status": "error", "message": "Name and IP are required"}), 400
        
        # Check if device already exists
        if new_device['name'] in devices:
            return jsonify({"status": "error", "message": "Device already exists"}), 400
        
        devices[new_device['name']] = new_device['ip']
        save_devices(devices)
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/devices', methods=['DELETE'])
def delete_device():
    try:
        devices = load_devices()
        device_data = request.get_json()
        
        if not device_data.get('name'):
            return jsonify({"status": "error", "message": "Device name is required"}), 400
        
        device_name = device_data['name']
        
        if device_name not in devices:
            return jsonify({"status": "error", "message": "Device not found"}), 404
        
        del devices[device_name]
        save_devices(devices)
        
        # Also remove from history
        history = load_history()
        if device_name in history:
            del history[device_name]
            save_history(history)
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/history/<device_name>')
def get_device_history(device_name):
    try:
        history = load_history()
        if device_name in history:
            return jsonify(history[device_name])
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    try:
        with file_lock:
            with open(DATA_FILE) as f:
                data = json.load(f)
        
        total = len(data.get('devices', {}))
        online = sum(1 for d in data.get('devices', {}).values() if d.get('reachable', False))
        offline = total - online
        
        latencies = [d['latency'] for d in data.get('devices', {}).values() 
                    if d.get('reachable', False) and d.get('latency')]
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        return jsonify({
            "total": total,
            "online": online,
            "offline": offline,
            "avg_latency": round(avg_latency, 2),
            "timestamp": data.get('timestamp', '')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure data directory exists
    os.makedirs('/app/data', exist_ok=True)
    
    # Initialize devices file if it doesn't exist
    if not os.path.exists(DEVICES_FILE):
        save_devices(load_devices())
    
    app.run(host='0.0.0.0', port=5000, debug=False)
