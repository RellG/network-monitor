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
import xml.etree.ElementTree as ET
import ipaddress
from collections import deque

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

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
UPTIME_FILE = "/app/data/uptime_stats.json"
SPEEDTEST_HISTORY_FILE = "/app/data/speed_test_history.json"
MAX_SPEEDTEST_HISTORY = 50
SCAN_RESULTS_FILE = "/app/data/scan_results.json"
SCAN_HISTORY_FILE = "/app/data/scan_history.json"
MAX_SCAN_HISTORY = 10

IP_PATTERN = re.compile(r'^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$')

file_lock = threading.Lock()

# Scan state (in-memory)
scan_state = {
    "status": "idle",
    "progress": 0,
    "message": "",
    "started_at": None,
    "completed_at": None,
    "subnet": None
}
scan_lock = threading.Lock()

# Speed test state
speedtest_state = {
    "status": "idle",
    "progress": 0,
    "message": "",
    "started_at": None,
    "completed_at": None
}
speedtest_lock = threading.Lock()

# Bandwidth monitoring
bandwidth_data = deque(maxlen=300)  # 10 min at 2s intervals
bandwidth_lock = threading.Lock()


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


def migrate_device_entry(name, value):
    """Migrate a device entry from old format (string IP) to new format (dict)."""
    if isinstance(value, str):
        return {"ip": value, "tags": [], "notes": "", "category": "", "added_at": time.time()}
    return value


def get_device_ip(value):
    """Get IP from a device entry (supports old string and new dict formats)."""
    if isinstance(value, str):
        return value
    return value.get("ip", "")


def load_devices():
    devices = load_json(DEVICES_FILE)
    if not devices:
        default_devices_str = os.getenv('DEFAULT_DEVICES', '')
        if default_devices_str:
            devices = {}
            for pair in default_devices_str.split(','):
                if ':' in pair:
                    name, ip = pair.split(':', 1)
                    devices[name.strip()] = {"ip": ip.strip(), "tags": [], "notes": "", "category": "", "added_at": time.time()}
            return devices
    # Migrate old format entries
    migrated = False
    for name, value in devices.items():
        if isinstance(value, str):
            devices[name] = migrate_device_entry(name, value)
            migrated = True
    if migrated:
        save_json(DEVICES_FILE, devices)
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
    devices = load_devices()
    # Return a simplified view compatible with ping_monitor (name -> ip mapping)
    # but include full metadata
    return jsonify(devices)


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

    devices[name] = {
        "ip": ip,
        "tags": [],
        "notes": data.get('notes', '').strip(),
        "category": data.get('category', '').strip(),
        "added_at": time.time()
    }
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


@app.route('/api/devices/<name>', methods=['PATCH'])
def update_device(name):
    """Update device notes, tags, or category."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    devices = load_devices()
    if name not in devices:
        return jsonify({"status": "error", "message": "Device not found"}), 404

    device = devices[name]
    if 'notes' in data:
        notes = str(data['notes']).strip()
        if len(notes) > 500:
            return jsonify({"status": "error", "message": "Notes too long (max 500 chars)"}), 400
        device['notes'] = notes
    if 'tags' in data:
        tags = data['tags']
        if isinstance(tags, list):
            device['tags'] = [str(t).strip()[:32] for t in tags[:10]]
    if 'category' in data:
        device['category'] = str(data['category']).strip()[:32]

    devices[name] = device
    save_devices(devices)
    logger.info("Device updated: %s", name)
    return jsonify({"status": "success", "device": device})


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
        losses = [d.get('packet_loss', 0) for d in devices.values() if d.get('packet_loss') is not None]
        avg_loss = sum(losses) / len(losses) if losses else 0
        jitters = [d['jitter'] for d in devices.values() if d.get('jitter') is not None]
        avg_jitter = sum(jitters) / len(jitters) if jitters else 0

        return jsonify({
            "total": total,
            "online": online,
            "offline": total - online,
            "avg_latency": round(avg_latency, 2),
            "avg_packet_loss": round(avg_loss, 2),
            "avg_jitter": round(avg_jitter, 2),
            "timestamp": data.get('timestamp', '')
        })
    except Exception as e:
        logger.error("Error computing stats: %s", e)
        return jsonify({"total": 0, "online": 0, "offline": 0, "avg_latency": 0, "avg_packet_loss": 0, "avg_jitter": 0})


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
        return {
            "Example-Server": {"host": "192.168.1.100", "port": 22, "user": "admin", "description": "Example Server"}
        }
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


# ── Uptime Tracking ──────────────────────────────────

@app.route('/api/uptime/summary')
@cache.cached(timeout=5)
def get_uptime_summary():
    """Get fleet-wide uptime summary."""
    uptime = load_json(UPTIME_FILE)
    if not uptime:
        return jsonify({})
    summary = {}
    for name, data in uptime.items():
        summary[name] = {
            "today": data.get("today", {}).get("pct", 100.0),
            "week": data.get("week", {}).get("pct", 100.0),
            "month": data.get("month", {}).get("pct", 100.0),
            "current_state": data.get("current_state", "unknown"),
            "last_change": data.get("last_change", "")
        }
    return jsonify(summary)


@app.route('/api/uptime/<device_name>')
def get_device_uptime(device_name):
    """Get uptime stats for a specific device."""
    uptime = load_json(UPTIME_FILE)
    if device_name not in uptime:
        return jsonify({"error": "No uptime data for device"}), 404
    return jsonify(uptime[device_name])


# ── Network Scanner ──────────────────────────────────

def detect_subnet():
    """Auto-detect the local subnet from network interfaces."""
    try:
        result = subprocess.run(
            ["ip", "-4", "addr", "show"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if 'inet ' in line and '127.0.0.1' not in line:
                addr_cidr = line.split()[1]
                network = ipaddress.IPv4Network(addr_cidr, strict=False)
                return str(network)
    except Exception as e:
        logger.warning("Subnet detection failed: %s", e)
    return "192.168.1.0/24"


def get_arp_table():
    """Read ARP table from ip neigh to get MAC addresses."""
    arp = {}
    try:
        result = subprocess.run(
            ["ip", "neigh"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[2] == 'lladdr':
                # Format: "192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"
                ip = parts[0]
                mac = parts[4].upper()
                arp[ip] = mac
            elif len(parts) >= 5 and 'lladdr' in parts:
                idx = parts.index('lladdr')
                if idx + 1 < len(parts):
                    arp[parts[0]] = parts[idx + 1].upper()
    except Exception as e:
        logger.warning("ARP table read failed: %s", e)
    return arp


def lookup_mac_vendor(mac):
    """Look up vendor from MAC prefix using nmap's OUI database."""
    if not mac:
        return ""
    prefix = mac.upper().replace(':', '')[:6]
    oui_file = "/usr/share/nmap/nmap-mac-prefixes"
    try:
        with open(oui_file) as f:
            for line in f:
                if line.startswith(prefix):
                    return line.strip().split(' ', 1)[1] if ' ' in line.strip() else ''
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return ""


def parse_nmap_xml(xml_string):
    """Parse nmap XML output into a list of host dicts."""
    hosts = []
    try:
        root = ET.fromstring(xml_string)
        for host_el in root.findall('host'):
            status_el = host_el.find('status')
            if status_el is None or status_el.get('state') != 'up':
                continue
            host = {
                "ip": "", "hostname": "", "mac": "", "vendor": "",
                "status": "up", "latency": None, "ports": []
            }
            for addr in host_el.findall('address'):
                if addr.get('addrtype') == 'ipv4':
                    host["ip"] = addr.get('addr', '')
                elif addr.get('addrtype') == 'mac':
                    host["mac"] = addr.get('addr', '')
                    host["vendor"] = addr.get('vendor', '')
            hostnames_el = host_el.find('hostnames')
            if hostnames_el is not None:
                hn = hostnames_el.find('hostname')
                if hn is not None:
                    host["hostname"] = hn.get('name', '')
            times_el = host_el.find('times')
            if times_el is not None:
                srtt = times_el.get('srtt')
                if srtt:
                    host["latency"] = round(int(srtt) / 1000, 2)
            ports_el = host_el.find('ports')
            if ports_el is not None:
                for port_el in ports_el.findall('port'):
                    state_el = port_el.find('state')
                    if state_el is not None and state_el.get('state') == 'open':
                        service_el = port_el.find('service')
                        host["ports"].append({
                            "port": int(port_el.get('portid', 0)),
                            "protocol": port_el.get('protocol', 'tcp'),
                            "service": service_el.get('name', '') if service_el is not None else '',
                            "product": service_el.get('product', '') if service_el is not None else ''
                        })
            hosts.append(host)
    except ET.ParseError as e:
        logger.error("nmap XML parse error: %s", e)
    return hosts


def categorize_device(host):
    """Categorize a device based on open ports and vendor string."""
    vendor = (host.get("vendor") or "").lower()
    ports = {p["port"] for p in host.get("ports", [])}
    hostname = (host.get("hostname") or "").lower()

    if any(k in vendor for k in ["cisco", "ubiquiti", "netgear", "tp-link", "asus", "eero"]):
        return "router"
    if any(k in vendor for k in ["raspberry"]):
        return "pi"
    if any(k in hostname for k in ["rpi", "raspberry", "pi"]):
        return "pi"
    if 80 in ports or 443 in ports or 8080 in ports:
        return "server"
    if 22 in ports:
        return "server"
    if any(k in vendor for k in ["espressif", "tuya", "shelly", "sonoff"]):
        return "iot"
    if any(k in vendor for k in ["sony", "microsoft", "nintendo"]):
        return "iot"
    if any(k in vendor for k in ["apple", "samsung", "google", "oneplus", "xiaomi", "huawei"]):
        return "mobile"
    return "unknown"


def run_network_scan(subnet, port_scan=False):
    """Execute nmap scan in background thread."""
    global scan_state

    with scan_lock:
        scan_state["status"] = "running"
        scan_state["progress"] = 10
        scan_state["message"] = f"Scanning {subnet} for live hosts..."
        scan_state["started_at"] = time.time()
        scan_state["subnet"] = subnet

    try:
        result = subprocess.run(
            ["nmap", "-sn", "-oX", "-", subnet],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            with scan_lock:
                scan_state["status"] = "error"
                scan_state["message"] = f"nmap failed: {result.stderr[:200]}"
            return

        hosts = parse_nmap_xml(result.stdout)

        with scan_lock:
            scan_state["progress"] = 50
            scan_state["message"] = f"Found {len(hosts)} hosts"

        if port_scan and hosts:
            live_ips = [h["ip"] for h in hosts if h["ip"]]
            total = len(live_ips)
            for idx, ip in enumerate(live_ips):
                with scan_lock:
                    pct = 50 + int((idx / max(total, 1)) * 45)
                    scan_state["progress"] = pct
                    scan_state["message"] = f"Port scanning {ip} ({idx+1}/{total})..."
                try:
                    port_result = subprocess.run(
                        ["nmap", "-sV", "-F", "--open", "-oX", "-", ip],
                        capture_output=True, text=True, timeout=30
                    )
                    if port_result.returncode == 0:
                        port_hosts = parse_nmap_xml(port_result.stdout)
                        if port_hosts:
                            for h in hosts:
                                if h["ip"] == ip:
                                    h["ports"] = port_hosts[0].get("ports", [])
                                    break
                except subprocess.TimeoutExpired:
                    logger.warning("Port scan timed out for %s", ip)

        # Enrich with ARP table MAC addresses and vendor lookup
        arp_table = get_arp_table()
        for h in hosts:
            if not h["mac"] and h["ip"] in arp_table:
                h["mac"] = arp_table[h["ip"]]
            if h["mac"] and not h["vendor"]:
                h["vendor"] = lookup_mac_vendor(h["mac"])

        for h in hosts:
            h["device_type"] = categorize_device(h)

        previous = load_json(SCAN_RESULTS_FILE, {"hosts": []})
        previous_ips = {h["ip"] for h in previous.get("hosts", [])}
        current_ips = {h["ip"] for h in hosts}

        scan_results = {
            "subnet": subnet,
            "timestamp": time.time(),
            "host_count": len(hosts),
            "hosts": hosts,
            "new_hosts": [h["ip"] for h in hosts if h["ip"] not in previous_ips],
            "missing_hosts": list(previous_ips - current_ips)
        }
        save_json(SCAN_RESULTS_FILE, scan_results)

        history = load_json(SCAN_HISTORY_FILE, [])
        history.append({
            "timestamp": time.time(),
            "subnet": subnet,
            "host_count": len(hosts),
            "new_count": len(scan_results["new_hosts"]),
            "missing_count": len(scan_results["missing_hosts"])
        })
        if len(history) > MAX_SCAN_HISTORY:
            history = history[-MAX_SCAN_HISTORY:]
        save_json(SCAN_HISTORY_FILE, history)

        with scan_lock:
            scan_state["status"] = "complete"
            scan_state["progress"] = 100
            scan_state["message"] = f"Scan complete: {len(hosts)} hosts found"
            scan_state["completed_at"] = time.time()

    except subprocess.TimeoutExpired:
        with scan_lock:
            scan_state["status"] = "error"
            scan_state["message"] = "Scan timed out"
    except Exception as e:
        logger.error("Scan error: %s", e)
        with scan_lock:
            scan_state["status"] = "error"
            scan_state["message"] = str(e)[:200]


@app.route('/api/scan', methods=['POST'])
def start_scan():
    """Start a network scan."""
    with scan_lock:
        if scan_state["status"] == "running":
            return jsonify({"status": "error", "message": "Scan already in progress"}), 409

    data = request.get_json(silent=True) or {}
    subnet = (data.get('subnet') or '').strip()
    port_scan = data.get('port_scan', False)

    if not subnet:
        subnet = detect_subnet()

    try:
        net = ipaddress.IPv4Network(subnet, strict=False)
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid subnet format"}), 400

    if net.prefixlen < 24:
        return jsonify({"status": "error", "message": "Subnet too large (minimum /24)"}), 400

    thread = threading.Thread(target=run_network_scan, args=(subnet, port_scan), daemon=True)
    thread.start()
    logger.info("Network scan started: %s (ports=%s)", subnet, port_scan)
    return jsonify({"status": "success", "message": f"Scan started for {subnet}", "subnet": subnet})


@app.route('/api/scan/status')
def get_scan_status():
    """Get current scan status."""
    with scan_lock:
        return jsonify(dict(scan_state))


@app.route('/api/scan/results')
def get_scan_results():
    """Get latest scan results."""
    results = load_json(SCAN_RESULTS_FILE, {"hosts": [], "host_count": 0})
    return jsonify(results)


@app.route('/api/scan/history')
def get_scan_history():
    """Get scan history."""
    history = load_json(SCAN_HISTORY_FILE, [])
    return jsonify(history)


@app.route('/api/scan/port/<ip>')
def quick_port_scan(ip):
    """Quick port scan on a single IP."""
    if not IP_PATTERN.match(ip):
        return jsonify({"error": "Invalid IP"}), 400
    try:
        result = subprocess.run(
            ["nmap", "-sV", "-F", "--open", "-oX", "-", ip],
            capture_output=True, text=True, timeout=30
        )
        hosts = parse_nmap_xml(result.stdout)
        if hosts:
            return jsonify({"ip": ip, "ports": hosts[0].get("ports", [])})
        return jsonify({"ip": ip, "ports": []})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Scan timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Speed Test ───────────────────────────────────────

def run_speed_test():
    """Execute speed test in background thread."""
    global speedtest_state
    with speedtest_lock:
        speedtest_state["status"] = "running"
        speedtest_state["progress"] = 10
        speedtest_state["message"] = "Connecting to server..."
        speedtest_state["started_at"] = time.time()

    try:
        result = subprocess.run(
            ["python3", "-m", "speedtest", "--json"],
            capture_output=True, text=True, timeout=120
        )

        with speedtest_lock:
            speedtest_state["progress"] = 50
            speedtest_state["message"] = "Processing results..."

        if result.returncode != 0:
            with speedtest_lock:
                speedtest_state["status"] = "error"
                speedtest_state["message"] = "Speed test failed: " + (result.stderr[:200] if result.stderr else "unknown error")
            return

        data = json.loads(result.stdout)
        test_result = {
            "timestamp": time.time(),
            "download_mbps": round(data.get("download", 0) / 1_000_000, 2),
            "upload_mbps": round(data.get("upload", 0) / 1_000_000, 2),
            "ping_ms": round(data.get("ping", 0), 2),
            "server": data.get("server", {}).get("sponsor", "") + " - " + data.get("server", {}).get("name", ""),
            "server_location": data.get("server", {}).get("country", ""),
            "isp": data.get("client", {}).get("isp", "")
        }

        # Save to history
        history = load_json(SPEEDTEST_HISTORY_FILE, [])
        history.append(test_result)
        if len(history) > MAX_SPEEDTEST_HISTORY:
            history = history[-MAX_SPEEDTEST_HISTORY:]
        save_json(SPEEDTEST_HISTORY_FILE, history)

        with speedtest_lock:
            speedtest_state["status"] = "complete"
            speedtest_state["progress"] = 100
            speedtest_state["message"] = f"Download: {test_result['download_mbps']} Mbps, Upload: {test_result['upload_mbps']} Mbps"
            speedtest_state["completed_at"] = time.time()
            speedtest_state["result"] = test_result

    except subprocess.TimeoutExpired:
        with speedtest_lock:
            speedtest_state["status"] = "error"
            speedtest_state["message"] = "Speed test timed out"
    except json.JSONDecodeError:
        with speedtest_lock:
            speedtest_state["status"] = "error"
            speedtest_state["message"] = "Failed to parse speed test results"
    except Exception as e:
        logger.error("Speed test error: %s", e)
        with speedtest_lock:
            speedtest_state["status"] = "error"
            speedtest_state["message"] = str(e)[:200]


@app.route('/api/speedtest', methods=['POST'])
def start_speed_test():
    """Start a speed test."""
    with speedtest_lock:
        if speedtest_state["status"] == "running":
            return jsonify({"status": "error", "message": "Speed test already running"}), 409

    thread = threading.Thread(target=run_speed_test, daemon=True)
    thread.start()
    logger.info("Speed test started")
    return jsonify({"status": "success", "message": "Speed test started"})


@app.route('/api/speedtest/status')
def get_speedtest_status():
    """Get speed test status."""
    with speedtest_lock:
        return jsonify(dict(speedtest_state))


@app.route('/api/speedtest/history')
def get_speedtest_history():
    """Get speed test history."""
    history = load_json(SPEEDTEST_HISTORY_FILE, [])
    return jsonify(history)


# ── Bandwidth Monitoring ─────────────────────────────

def bandwidth_monitor_loop():
    """Background thread to sample bandwidth every 2 seconds."""
    if not PSUTIL_AVAILABLE:
        logger.warning("psutil not available, bandwidth monitoring disabled")
        return
    prev = psutil.net_io_counters()
    prev_time = time.time()
    while True:
        time.sleep(2)
        try:
            curr = psutil.net_io_counters()
            curr_time = time.time()
            dt = curr_time - prev_time
            if dt > 0:
                rx_mbps = round((curr.bytes_recv - prev.bytes_recv) * 8 / dt / 1_000_000, 3)
                tx_mbps = round((curr.bytes_sent - prev.bytes_sent) * 8 / dt / 1_000_000, 3)
                with bandwidth_lock:
                    bandwidth_data.append({
                        "timestamp": curr_time,
                        "rx_mbps": rx_mbps,
                        "tx_mbps": tx_mbps
                    })
            prev = curr
            prev_time = curr_time
        except Exception as e:
            logger.error("Bandwidth sampling error: %s", e)


@app.route('/api/bandwidth')
@cache.cached(timeout=1)
def get_bandwidth():
    """Get bandwidth data."""
    with bandwidth_lock:
        data = list(bandwidth_data)
    current = data[-1] if data else {"rx_mbps": 0, "tx_mbps": 0, "timestamp": 0}
    return jsonify({"current": current, "history": data})


@app.route('/api/bandwidth/interfaces')
@cache.cached(timeout=30)
def get_bandwidth_interfaces():
    """List network interfaces."""
    if not PSUTIL_AVAILABLE:
        return jsonify([])
    interfaces = []
    for name, addrs in psutil.net_if_addrs().items():
        if name == 'lo':
            continue
        ips = [a.address for a in addrs if a.family == 2]  # AF_INET
        interfaces.append({"name": name, "ips": ips})
    return jsonify(interfaces)


if __name__ == '__main__':
    os.makedirs('/app/data', exist_ok=True)
    if not os.path.exists(DEVICES_FILE):
        save_devices(load_devices())
    if not os.path.exists(SERVERS_FILE):
        save_servers(load_servers())
    if not os.path.exists(SCAN_RESULTS_FILE):
        save_json(SCAN_RESULTS_FILE, {"hosts": [], "host_count": 0})

    # Start bandwidth monitoring thread
    bw_thread = threading.Thread(target=bandwidth_monitor_loop, daemon=True)
    bw_thread.start()

    logger.info("Starting Network Monitor API server on :5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
