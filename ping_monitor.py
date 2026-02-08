#!/usr/bin/env python3
import subprocess
import time
import json
import os
import re
import threading
import concurrent.futures
import statistics
from datetime import datetime
from collections import deque

LOG_FILE = "/app/data/ping_data.json"
DEVICES_FILE = "/app/data/devices.json"
HISTORY_FILE = "/app/data/ping_history.json"
UPTIME_FILE = "/app/data/uptime_stats.json"

# Configuration (env-configurable)
MAX_HISTORY_POINTS = int(os.getenv('MAX_HISTORY_POINTS', '1800'))  # 30 min at 2s interval
PING_INTERVAL = int(os.getenv('PING_INTERVAL', '2'))  # seconds between cycles
PING_TIMEOUT = float(os.getenv('PING_TIMEOUT', '0.5'))  # timeout per ping
PING_COUNT = int(os.getenv('PING_COUNT', '5'))  # pings per check
MAX_WORKERS = 10  # Maximum concurrent ping operations

# Lock for thread-safe file operations
file_lock = threading.Lock()

# Regex to extract individual RTT values from ping output
RTT_PATTERN = re.compile(r'time[=<]([\d.]+)\s*ms')
LOSS_PATTERN = re.compile(r'(\d+)% packet loss')


class PingMonitor:
    def __init__(self):
        self.history = self.load_history()
        self.uptime = self.load_uptime()
        self.previous_state = {}  # Track online/offline for state change detection

    def load_history(self):
        """Load historical data from file"""
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                return {k: deque(v, maxlen=MAX_HISTORY_POINTS) for k, v in data.items()}
        except:
            return {}

    def save_history(self):
        """Save historical data to file"""
        with file_lock:
            data = {k: list(v) for k, v in self.history.items()}
            with open(HISTORY_FILE, 'w') as f:
                json.dump(data, f)

    def load_uptime(self):
        """Load uptime stats from file"""
        try:
            with open(UPTIME_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}

    def save_uptime(self):
        """Save uptime stats to file"""
        with file_lock:
            with open(UPTIME_FILE, 'w') as f:
                json.dump(self.uptime, f, indent=2)

    def ping_device(self, ip):
        """Ping a device and return latency, packet loss, and jitter"""
        try:
            result = subprocess.run(
                ["ping", "-c", str(PING_COUNT), "-W", str(int(PING_TIMEOUT * 1000)) if PING_TIMEOUT < 1 else str(int(PING_TIMEOUT)), ip],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=PING_COUNT * PING_TIMEOUT + 5
            )

            output = result.stdout

            # Extract individual RTT values
            rtts = [float(m) for m in RTT_PATTERN.findall(output)]

            # Extract packet loss percentage
            loss_match = LOSS_PATTERN.search(output)
            packet_loss = float(loss_match.group(1)) if loss_match else (0.0 if rtts else 100.0)

            # Calculate stats
            if rtts:
                avg_latency = round(statistics.mean(rtts), 2)
                jitter = round(statistics.stdev(rtts), 2) if len(rtts) > 1 else 0.0
                return {
                    "reachable": True,
                    "latency": avg_latency,
                    "packet_loss": packet_loss,
                    "jitter": jitter,
                    "packets_sent": PING_COUNT,
                    "packets_received": len(rtts)
                }
            else:
                return {
                    "reachable": False,
                    "latency": None,
                    "packet_loss": 100.0,
                    "jitter": None,
                    "packets_sent": PING_COUNT,
                    "packets_received": 0
                }

        except subprocess.TimeoutExpired:
            return {
                "reachable": False, "latency": None,
                "packet_loss": 100.0, "jitter": None,
                "packets_sent": PING_COUNT, "packets_received": 0
            }
        except Exception as e:
            print(f"Error pinging {ip}: {e}")
            return {
                "reachable": False, "latency": None,
                "packet_loss": 100.0, "jitter": None,
                "packets_sent": PING_COUNT, "packets_received": 0
            }

    def load_devices(self):
        """Load devices from configuration file, returning {name: ip} mapping"""
        try:
            with open(DEVICES_FILE, 'r') as f:
                raw = json.load(f)
            # Support both old format {name: "ip"} and new format {name: {ip: "ip", ...}}
            result = {}
            for name, value in raw.items():
                if isinstance(value, str):
                    result[name] = value
                elif isinstance(value, dict):
                    result[name] = value.get("ip", "")
                else:
                    continue
            return result
        except:
            return {}

    def update_history(self, device_name, ping_result):
        """Update historical data for a device"""
        if device_name not in self.history:
            self.history[device_name] = deque(maxlen=MAX_HISTORY_POINTS)

        self.history[device_name].append({
            "timestamp": datetime.now().isoformat(),
            "latency": ping_result["latency"],
            "packet_loss": ping_result["packet_loss"],
            "jitter": ping_result["jitter"]
        })

    def update_uptime(self, device_name, reachable):
        """Update uptime tracking for a device"""
        now = datetime.now()
        today_key = now.strftime('%Y-%m-%d')
        week_key = now.strftime('%Y-W%W')
        month_key = now.strftime('%Y-%m')

        if device_name not in self.uptime:
            self.uptime[device_name] = {
                "today": {"date": today_key, "checks": 0, "online": 0, "pct": 100.0},
                "week": {"key": week_key, "checks": 0, "online": 0, "pct": 100.0},
                "month": {"key": month_key, "checks": 0, "online": 0, "pct": 100.0},
                "current_state": "unknown",
                "last_change": now.isoformat(),
                "downtime_events": []
            }

        dev = self.uptime[device_name]

        # Reset counters if period changed
        if dev["today"].get("date") != today_key:
            dev["today"] = {"date": today_key, "checks": 0, "online": 0, "pct": 100.0}
        if dev["week"].get("key") != week_key:
            dev["week"] = {"key": week_key, "checks": 0, "online": 0, "pct": 100.0}
        if dev["month"].get("key") != month_key:
            dev["month"] = {"key": month_key, "checks": 0, "online": 0, "pct": 100.0}

        # Increment counters
        for period in ["today", "week", "month"]:
            dev[period]["checks"] += 1
            if reachable:
                dev[period]["online"] += 1
            dev[period]["pct"] = round(
                (dev[period]["online"] / dev[period]["checks"]) * 100, 2
            ) if dev[period]["checks"] > 0 else 100.0

        # Track state transitions
        prev_state = dev.get("current_state", "unknown")
        new_state = "online" if reachable else "offline"

        if prev_state != new_state and prev_state != "unknown":
            dev["last_change"] = now.isoformat()
            if new_state == "offline":
                # Started a downtime event
                dev["downtime_events"].append({
                    "start": now.isoformat(),
                    "end": None,
                    "duration_sec": None
                })
            elif new_state == "online" and dev["downtime_events"]:
                # End the most recent downtime event
                last_event = dev["downtime_events"][-1]
                if last_event["end"] is None:
                    last_event["end"] = now.isoformat()
                    try:
                        start_dt = datetime.fromisoformat(last_event["start"])
                        last_event["duration_sec"] = int((now - start_dt).total_seconds())
                    except:
                        last_event["duration_sec"] = 0

        dev["current_state"] = new_state

        # Keep only last 50 downtime events
        if len(dev["downtime_events"]) > 50:
            dev["downtime_events"] = dev["downtime_events"][-50:]

    def clean_history(self, current_devices):
        """Remove history for devices that no longer exist"""
        devices_to_remove = [name for name in self.history if name not in current_devices]
        for name in devices_to_remove:
            del self.history[name]

    def ping_device_wrapper(self, name, ip):
        """Wrapper for parallel ping execution"""
        ping_result = self.ping_device(ip)
        return name, {**ping_result, "ip": ip}, ping_result

    def run(self):
        """Main monitoring loop with parallel ping execution"""
        print(f"Starting ping monitor (count={PING_COUNT}, interval={PING_INTERVAL}s, timeout={PING_TIMEOUT}s)...")

        while True:
            try:
                devices = self.load_devices()

                if not devices:
                    time.sleep(PING_INTERVAL)
                    continue

                self.clean_history(devices)

                results = {
                    "timestamp": datetime.now().isoformat(),
                    "devices": {}
                }

                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    future_to_device = {
                        executor.submit(self.ping_device_wrapper, name, ip): name
                        for name, ip in devices.items()
                    }

                    for future in concurrent.futures.as_completed(future_to_device):
                        try:
                            name, device_data, ping_result = future.result()
                            results["devices"][name] = device_data
                            self.update_history(name, ping_result)
                            self.update_uptime(name, ping_result["reachable"])
                        except Exception as e:
                            device_name = future_to_device[future]
                            print(f"Error pinging {device_name}: {e}")

                if results["devices"]:
                    with file_lock:
                        with open(LOG_FILE, 'w') as f:
                            json.dump(results, f, indent=2)

                # Save history and uptime periodically (every 10 seconds)
                if int(time.time()) % 10 == 0:
                    self.save_history()
                    self.save_uptime()

            except Exception as e:
                print(f"Error in monitoring loop: {e}")

            time.sleep(PING_INTERVAL)


def main():
    """Initialize and start the monitor"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    monitor = PingMonitor()

    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        monitor.save_history()
        monitor.save_uptime()
        print("Monitor stopped.")

if __name__ == "__main__":
    main()
