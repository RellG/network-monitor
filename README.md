# LatencyMonitor - Network Monitoring Platform

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](#quick-start)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)

An enterprise-grade network monitoring platform with real-time latency tracking, server management, and a modern dashboard UI. Designed for homelab and small infrastructure environments.

## Features

- **Real-time Ping Monitoring** - Parallel ping execution with 2-second refresh intervals
- **Server Management** - SSH server tracking with live ping/SSH port status checks
- **Enterprise Dashboard** - Sidebar navigation, KPI cards, sparkline charts, dark/light theme
- **Diff-based Rendering** - Efficient DOM updates without full page re-renders
- **Device Management** - Add/remove devices via the web UI with IP validation
- **Search, Filter & Sort** - Debounced search, category filtering, multi-field sorting
- **Webhook Alerts** - Discord/Slack notifications when devices go offline
- **Docker Healthcheck** - Built-in `/api/health` endpoint with container health monitoring
- **Responsive Design** - Works on desktop, tablet, and mobile

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/RellG/network-monitor.git
cd network-monitor
docker compose up -d
```

Access the dashboard at `http://localhost:8082`

### Manual

```bash
pip install -r requirements.txt
python ping_monitor.py &
python app.py
```

Access the dashboard at `http://localhost:5000`

## Configuration

All configuration is optional. Copy `.env.example` to `.env` to customize:

```bash
# Default devices (format: "Name1:IP1,Name2:IP2")
DEFAULT_DEVICES=Router:192.168.1.1,NAS:192.168.1.50

# Webhook for offline alerts (Discord, Slack, etc.)
WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN

# Optional platform integration URLs
AI_SERVER_URL=
LOGGING_SERVER_URL=
PLATFORM_MONITOR_URL=
PLATFORM_LOGS_URL=
PLATFORM_AI_URL=
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Dashboard      │◄───┤   Flask API      ├───►│  Ping Monitor   │
│  (Single-file)   │    │  (app.py)        │    │  (Background)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Webhook Alerts  │    │  Server Checks   │    │  JSON Storage   │
│  (Optional)      │    │  (SSH + Ping)    │    │  (data/*.json)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Core Files
| File | Description |
|------|-------------|
| `app.py` | Flask API server with structured logging and input validation |
| `ping_monitor.py` | Background ping service using ThreadPoolExecutor |
| `Templates/dashboard.html` | Enterprise dashboard (HTML/CSS/JS, single file) |
| `nginx.conf` | Reverse proxy with gzip, caching, and security headers |
| `docker-compose.yml` | Container orchestration (Flask + nginx) |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/data` | Current ping data for all devices |
| GET | `/api/stats` | Aggregate network statistics |
| GET | `/api/health` | Health check (Docker healthcheck) |
| GET | `/api/config` | Platform configuration |
| GET | `/api/devices` | List monitored devices |
| POST | `/api/devices` | Add device `{name, ip}` |
| DELETE | `/api/devices` | Remove device `{name}` |
| GET | `/api/history/<name>` | Latency history for a device |
| GET | `/api/servers` | List servers with live status |
| POST | `/api/servers` | Add server `{name, host, port, user}` |
| DELETE | `/api/servers/<name>` | Remove a server |
| GET | `/api/servers/<name>/check` | Check single server status |

## Docker

The platform runs two containers via Docker Compose:

- **monitor** - Flask app + ping monitor (port 5000 internal)
- **nginx** - Reverse proxy (port 8082 external)

```bash
# Build and start
docker compose up -d

# View logs
docker compose logs -f monitor

# Rebuild after changes
docker compose build && docker compose up -d
```

The monitor container requires `NET_RAW` and `NET_ADMIN` capabilities for ping operations.

## Troubleshooting

```bash
# Check container health
docker compose ps

# View application logs
docker compose logs -f monitor

# Full rebuild
docker compose down && docker compose build --no-cache && docker compose up -d
```

## License

MIT License - see LICENSE file for details.
