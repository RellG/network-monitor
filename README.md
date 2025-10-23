# 🌐 LatencyMonitor - AI-Enhanced Network Monitoring Platform

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](#docker-deployment-recommended)
[![AI](https://img.shields.io/badge/AI-Enhanced-purple)](#ai-powered-intelligence)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)

A **modern network monitoring platform** featuring AI-powered insights, real-time topology mapping, and optional integrations for enhanced functionality.

## ✨ Features

### 🤖 AI-Powered Intelligence
- **External AI Integration**: Connect to your own AI server for advanced network analysis
- **Smart Recommendations**: Context-aware network optimization suggestions
- **Performance Scoring**: AI-driven network health assessment (0-100)
- **Local Fallback**: Built-in analysis when external AI is unavailable
- **Predictive Insights**: Quality, stability, and jitter analysis per device

### 📊 Network Topology & Visualization
- **Interactive Network Map**: Visual representation of your network
- **Device Classification**: Auto-categorizes as Router, Pi, IoT, or Server
- **Real-time Connections**: Live status with color-coded connection lines
- **Responsive Sparklines**: Beautiful latency trend charts

### 🎨 Modern UI/UX
- **Dark/Light Theme Toggle**: Easy on the eyes during day/night monitoring
- **Quiet Hours Mode**: Auto-dimming interface (11PM-7AM)
- **Device Categories**: Smart filtering by device type
- **Uptime Tracking**: Real-time device uptime counters
- **Mobile Responsive**: Perfect for monitoring on-the-go

### 🔗 Optional Integrations (All Non-Disruptive)
- **Webhook Alerts**: Real-time notifications for device status changes (Discord, Slack, etc.)
- **Logging Integration**: Silent event logging to external logging systems
- **Browser Notifications**: Desktop alerts for critical events
- **External AI Server**: Advanced network analysis via REST API

## 🚀 Quick Start

### Docker Deployment (Recommended)
```bash
git clone https://github.com/YOUR_USERNAME/LatencyMonitor.git
cd LatencyMonitor
docker-compose up -d
```

Access the dashboard at: `http://localhost:8082`

### Manual Setup
```bash
pip install -r requirements.txt
python ping_monitor.py &
python app.py
```

Access the dashboard at: `http://localhost:5000`

## 📋 Configuration

All configuration is **optional** and done via environment variables. Copy `.env.example` to `.env` and configure as needed:

### Environment Variables

```bash
# Default Devices (optional)
# Format: "DeviceName1:IP1,DeviceName2:IP2"
DEFAULT_DEVICES=Router:192.168.1.1,Server:192.168.1.100

# AI Analysis Server (optional)
# Your external AI server for advanced network analysis
AI_SERVER_URL=http://your-ai-server:8080

# Logging Server (optional)
# External logging server for centralized event logging
LOGGING_SERVER_URL=http://your-logging-server:3000

# Webhook URL (optional)
# Webhook for real-time alerts (Discord, Slack, etc.)
WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN

# Platform URLs (optional)
# Display connected platforms in the AI sidebar
PLATFORM_MONITOR_URL=http://localhost:8082
PLATFORM_LOGS_URL=http://your-logging-server:3000
PLATFORM_AI_URL=http://your-ai-server:8080
```

### Device Management
- Add devices via the web interface (no configuration files needed)
- Automatic categorization based on hostname and IP
- Persistent device history and uptime tracking
- Export/import device configurations

## 🎯 Key Components

### Core Files
- `app.py`: Flask web server and API endpoints
- `ping_monitor.py`: Background network monitoring service
- `Templates/dashboard.html`: AI-powered web interface
- `docker-compose.yml`: Container orchestration
- `requirements.txt`: Python dependencies

### Features
- **Real-time Monitoring**: 2-second refresh intervals
- **Historical Data**: 50-point latency history per device
- **Smart Alerts**: Configurable thresholds (default: >200ms latency)
- **Data Persistence**: Docker volume for device configurations
- **Graceful Degradation**: All integrations are optional and non-disruptive

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Interface │◄───┤   Flask Server   ├───►│ Ping Monitor    │
│  (AI Enhanced)  │    │  (API Endpoints) │    │ (Background)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Webhook Alerts  │    │   AI Server      │    │ Device History  │
│ (Optional)      │    │   (Optional)     │    │ (JSON Storage)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🔧 Advanced Configuration

### External AI Server Integration
To enable advanced AI analysis, configure an AI server that implements the following endpoint:

**POST** `/api/tools/analyze_network`
```json
{
  "name": "analyze_network",
  "arguments": {
    "devices": ["Device1", "Device2"],
    "latency_data": {
      "Device1": [10.5, 11.2, 10.8],
      "Device2": [25.3, 26.1, 24.9]
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "network_score": 85,
  "status": "good",
  "recommendations": [
    "Network performance is within normal parameters",
    "Consider monitoring Device2 for latency spikes"
  ]
}
```

### Webhook Alert Integration
Configure a Discord webhook for real-time alerts:

1. Create a webhook in your Discord server settings
2. Add the webhook URL to your `.env` file:
   ```bash
   WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN
   ```
3. Restart the container: `docker-compose restart`

Slack and other webhook services are also supported (uses standard Discord webhook format).

### Custom Thresholds
Modify thresholds in `Templates/dashboard.html`:
```javascript
// Line ~1654: High latency threshold
if (device.latency > 200 && deviceHistory[name].length > 5) {
    // Adjust 200ms threshold as needed
}
```

## 📊 API Endpoints

- `GET /` - Web dashboard
- `GET /api/data` - Current device status
- `GET /api/devices` - List all monitored devices
- `POST /api/devices` - Add new device
- `DELETE /api/devices` - Remove device
- `GET /api/history/<device_name>` - Device latency history
- `GET /api/stats` - Network statistics summary
- `GET /api/config` - Frontend configuration

## 🐳 Docker Configuration

The platform uses Docker for easy deployment:

```yaml
version: '3'
services:
  monitor:
    build: .
    ports:
      - "8082:80"
    volumes:
      - ./data:/app/data
    environment:
      - AI_SERVER_URL=${AI_SERVER_URL}
      - WEBHOOK_URL=${WEBHOOK_URL}
    restart: unless-stopped
```

## 🛠️ Troubleshooting

### Container Issues
```bash
# Check container logs
docker-compose logs -f monitor

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Network Permissions
The container requires `NET_RAW` and `NET_ADMIN` capabilities for ping operations. These are configured in `docker-compose.yml`.

### Debug Mode
Add `?debug=1` to the URL to enable console logging for integrations:
```
http://localhost:8082/?debug=1
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with Flask and modern web technologies
- Designed for easy deployment and extensibility
- Inspired by the need for simple, effective network monitoring

## 📧 Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**Note**: All integrations (AI, webhooks, logging) are completely optional. The platform works perfectly as a standalone network monitor without any external services.
