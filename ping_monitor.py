#!/usr/bin/env python3
import subprocess
import time
import json
import os
import threading
import concurrent.futures
from datetime import datetime
from collections import deque

LOG_FILE = "/app/data/ping_data.json"
DEVICES_FILE = "/app/data/devices.json"
HISTORY_FILE = "/app/data/ping_history.json"

# Configuration
MAX_HISTORY_POINTS = 100  # Keep last 100 data points per device
PING_INTERVAL = 1  # seconds
PING_TIMEOUT = 1  # seconds
PING_COUNT = 1  # number of pings per check
MAX_WORKERS = 10  # Maximum concurrent ping operations

# Lock for thread-safe file operations
file_lock = threading.Lock()

class PingMonitor:
    def __init__(self):
        self.history = self.load_history()
        
    def load_history(self):
        """Load historical data from file"""
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                # Convert lists back to deques
                return {k: deque(v, maxlen=MAX_HISTORY_POINTS) for k, v in data.items()}
        except:
            return {}
    
    def save_history(self):
        """Save historical data to file"""
        with file_lock:
            # Convert deques to lists for JSON serialization
            data = {k: list(v) for k, v in self.history.items()}
            with open(HISTORY_FILE, 'w') as f:
                json.dump(data, f)
    
    def ping_device(self, ip):
        """Ping a device and return latency"""
        try:
            # Use subprocess to run ping command
            result = subprocess.run(
                ["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT), ip],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Parse the output to get latency
            if result.returncode == 0 and "time=" in result.stdout:
                # Extract latency from ping output
                latency_str = result.stdout.split("time=")[1].split()[0]
                latency = float(latency_str.replace("ms", ""))
                return {"reachable": True, "latency": latency}
            else:
                return {"reachable": False, "latency": None}
                
        except Exception as e:
            print(f"Error pinging {ip}: {e}")
            return {"reachable": False, "latency": None}
    
    def load_devices(self):
        """Load devices from configuration file"""
        try:
            with open(DEVICES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def update_history(self, device_name, latency):
        """Update historical data for a device"""
        if device_name not in self.history:
            self.history[device_name] = deque(maxlen=MAX_HISTORY_POINTS)
        
        self.history[device_name].append({
            "timestamp": datetime.now().isoformat(),
            "latency": latency
        })
    
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
        print("Starting optimized ping monitor with parallel execution...")

        while True:
            try:
                # Load current devices
                devices = self.load_devices()

                if not devices:
                    time.sleep(PING_INTERVAL)
                    continue

                # Clean up history for removed devices
                self.clean_history(devices)

                # Ping results
                results = {
                    "timestamp": datetime.now().isoformat(),
                    "devices": {}
                }

                # Ping devices in parallel for better performance
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    # Submit all ping tasks
                    future_to_device = {
                        executor.submit(self.ping_device_wrapper, name, ip): name
                        for name, ip in devices.items()
                    }

                    # Collect results as they complete
                    for future in concurrent.futures.as_completed(future_to_device):
                        try:
                            name, device_data, ping_result = future.result()
                            results["devices"][name] = device_data

                            # Update history if device is reachable
                            if ping_result["reachable"]:
                                self.update_history(name, ping_result["latency"])
                        except Exception as e:
                            device_name = future_to_device[future]
                            print(f"Error pinging {device_name}: {e}")

                # Save current results (only if we have data)
                if results["devices"]:
                    with file_lock:
                        with open(LOG_FILE, 'w') as f:
                            json.dump(results, f, indent=2)

                # Save history periodically (every 10 iterations)
                if int(time.time()) % 10 == 0:
                    self.save_history()

            except Exception as e:
                print(f"Error in monitoring loop: {e}")

            # Wait before next check
            time.sleep(PING_INTERVAL)

def main():
    """Initialize and start the monitor"""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    # Create and start monitor
    monitor = PingMonitor()
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        monitor.save_history()
        print("Monitor stopped.")

if __name__ == "__main__":
    main()
