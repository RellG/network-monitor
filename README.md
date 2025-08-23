# 🏠 Homelab LatencyMonitor - AI Enhanced Network Monitoring Platform

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](http://ping.rellcloud.online:8082)
[![AI](https://img.shields.io/badge/AI-Enhanced-purple?logo=brain)](https://github.com/RellG/nexus-mcp)
[![Discord](https://img.shields.io/badge/Discord-Alerts-7289da?logo=discord)](#)

A **next-generation network monitoring platform** built for homelabs, featuring AI-powered insights, real-time topology mapping, and seamless integrations with your existing infrastructure.

## ✨ Features

### 🤖 AI-Powered Intelligence
- **Nexus MCP Integration**: Real AI analysis with graceful fallbacks
- **Smart Recommendations**: Context-aware network optimization suggestions
- **Performance Scoring**: AI-driven network health assessment (0-100)
- **Predictive Insights**: Quality, stability, and jitter analysis per device

### 📊 Network Topology & Visualization
- **Interactive Network Map**: Visual representation of your homelab
- **Device Classification**: Auto-categorizes as Router, Pi, IoT, or Server
- **Real-time Connections**: Live status with color-coded connection lines
- **Responsive Sparklines**: Beautiful latency trend charts

### 🎨 Modern UI/UX
- **Dark/Light Theme Toggle**: Easy on the eyes during day/night monitoring
- **Quiet Hours Mode**: Auto-dimming interface (11PM-7AM)
- **Device Categories**: Smart filtering by device type
- **Uptime Tracking**: Real-time device uptime counters
- **Mobile Responsive**: Perfect for monitoring on-the-go

### 🔗 Seamless Integrations (All Non-Disruptive)
- **Discord Alerts**: Real-time notifications for device status changes
- **CyphorLogs Integration**: Silent event logging to your logging system
- **Browser Notifications**: Desktop alerts for critical events
- **Nexus MCP**: Advanced AI network analysis

## 🚀 Quick Start

### Docker Deployment (Recommended)
```bash
git clone https://github.com/RellG/network-monitor.git
cd network-monitor
docker-compose up -d
```

### Manual Setup
```bash
pip install -r requirements.txt
python ping_monitor.py &
python app.py
```

## 📋 Configuration

### Environment Variables
- `MCP_SERVER_URL`: Your Nexus Universal MCP Server (default: http://192.168.4.154:8080)
- `CYPHORLOGS_URL`: CyphorLogs integration endpoint (optional)
- `DISCORD_WEBHOOK_URL`: Discord webhook for alerts (optional)

### Device Management
- Add devices via the web interface
- Automatic categorization based on hostname and IP
- Persistent device history and uptime tracking

## 🎯 Key Components

### Core Files
- `app.py`: Flask web server and API endpoints
- `ping_monitor.py`: Background network monitoring service
- `Templates/dashboard.html`: Enhanced AI-powered web interface
- `docker-compose.yml`: Container orchestration
- `requirements.txt`: Python dependencies

### Features
- **Real-time Monitoring**: 2-second refresh intervals
- **Historical Data**: 50-point latency history per device
- **Smart Alerts**: Homelab-optimized thresholds (>200ms latency)
- **Data Persistence**: Docker volume for device configurations

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Interface │◄───┤   Flask Server   ├───►│ Ping Monitor    │
│  (AI Enhanced)  │    │  (API Endpoints) │    │ (Background)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Discord Alerts  │    │   Nexus MCP      │    │ Device History  │
│ (Non-disruptive)│    │ (AI Analysis)    │    │ (JSON Storage)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🔧 Advanced Configuration

### Nexus MCP Integration
To enable real AI analysis, ensure your [Nexus Universal MCP Server](https://github.com/RellG/nexus-mcp) is running:
```javascript
// In dashboard.html, update:
const MCP_SERVER_URL = 'http://your-mcp-server:8080';
```

### Discord Alerts Setup
1. Create a Discord webhook in your server
2. Update the webhook URL in `Templates/dashboard.html`:
```javascript
const DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/...';
```

### CyphorLogs Integration
For centralized logging, point to your CyphorLogs server:
```javascript
const CYPHORLOGS_URL = 'http://your-logs-server:3000';
```

## 🎨 Customization

### Device Categories
The system automatically categorizes devices:
- **🏠 Router**: Names containing 'router', 'gateway', or IPs ending in '.1'
- **🥧 Raspberry Pi**: Names containing 'pi' or 'raspberry'
- **🖥️ Server**: Names containing 'server', 'nas', or 'vm'
- **📱 IoT**: All other devices

### Theme Customization
Modify CSS variables in `Templates/dashboard.html`:
```css
:root {
  --accent: #3b82f6;          /* Primary accent color */
  --mcp-accent: #8b5cf6;      /* AI accent color */
  --ai-glow: #a855f7;         /* AI glow effect */
}
```

## 📊 API Endpoints

- `GET /`: Main dashboard interface
- `GET /api/data`: Current device data and latency
- `GET /api/devices`: List all configured devices
- `POST /api/devices`: Add new device
- `DELETE /api/devices`: Remove device

## 🛠️ Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run in development mode
export FLASK_ENV=development
python app.py
```

### Adding Features
The modular architecture makes it easy to extend:
1. Update `app.py` for new API endpoints
2. Modify `Templates/dashboard.html` for UI changes
3. Extend `ping_monitor.py` for monitoring enhancements

## 🔒 Security

- **No hardcoded secrets**: All sensitive data via environment variables
- **Non-disruptive integrations**: All external calls fail silently
- **Containerized**: Runs in isolated Docker environment
- **Read-only monitoring**: No network modifications, only observation

## 🤝 Integration Ecosystem

### Cyphor Homelab Stack
- **LatencyMonitor**: Network monitoring (this project)
- **CyphorLogs**: Centralized logging system
- **Nexus MCP**: AI analysis and automation
- **Discord**: Real-time alerting

## 📈 Performance

- **Lightweight**: <50MB Docker image
- **Fast**: 2-second refresh cycles
- **Efficient**: Minimal resource usage
- **Scalable**: Handles 50+ devices easily

## 🎯 Roadmap

- [ ] Historical trend analysis
- [ ] Network topology auto-discovery  
- [ ] Mobile PWA support
- [ ] SNMP integration
- [ ] Multi-site monitoring

## 📄 License

MIT License - Feel free to use this in your homelab!

## 🙏 Credits

- **AI Enhancement**: Powered by Claude Sonnet 4
- **Icons**: FontAwesome
- **Monitoring**: Python ICMP ping
- **UI Framework**: Vanilla JavaScript + CSS Grid
- **Container**: Docker + Flask

---

**🏠 Built with ❤️ for the homelab community**

Access your enhanced monitoring platform at: **http://ping.rellcloud.online:8082**