# Production Deployment Guide

Полное руководство по развертыванию в production.

---

## Обзор

Этот гайд покрывает:
- ✅ Pre-deployment проверки
- ✅ Установка и настройка
- ✅ Мониторинг и alerts
- ✅ Backup стратегия
- ✅ Security best practices
- ✅ Troubleshooting

---

## Pre-Deployment Checklist

### System Requirements

```yaml
Минимум:
  CPU: 2 cores
  RAM: 4GB
  Disk: 20GB
  Python: 3.10+

Рекомендуется:
  CPU: 4+ cores
  RAM: 8GB+
  Disk: 50GB+ (SSD)
  Python: 3.11+
```

### Software Dependencies

```bash
# Core
- Python 3.10+
- Ollama (latest)
- pip packages (see requirements.txt)

# Optional (monitoring)
- Prometheus 2.45+
- Grafana 9.0+
- prometheus-client (pip)

# Optional (deployment)
- systemd (Linux)
- Docker (optional)
```

---

## Installation

### 1. Базовая установка

```bash
# Clone repository
git clone https://github.com/your-org/digital-being.git
cd digital-being

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install optional monitoring
pip install prometheus-client
```

### 2. Установка Ollama

```bash
# Linux
curl https://ollama.ai/install.sh | sh

# Mac
brew install ollama

# Start Ollama
ollama serve &

# Pull models
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### 3. Конфигурация

```bash
# Copy example config
cp config.example.yaml config.yaml

# Edit config
nano config.yaml
```

**Ключевые настройки:**

```yaml
# config.yaml
ollama:
  base_url: "http://127.0.0.1:11434"
  strategy_model: "llama3.2:3b"
  embed_model: "nomic-embed-text"

# Cache (production tuning)
cache:
  max_size: 200  # Increase for production
  ttl_seconds: 600.0  # 10 min for production

# Rate limiting (adjust for your load)
rate_limit:
  chat_rate: 10.0  # 10 req/s for production
  chat_burst: 20
  embed_rate: 30.0
  embed_burst: 100

# API
api:
  enabled: true
  host: "0.0.0.0"  # Allow external connections
  port: 8766

# Logging
logging:
  level: "INFO"  # Use INFO in production
  dir: "logs"
```

### 4. Стартовая валидация

```bash
# Run startup validation
python -c "from core.startup_validator import validate_startup; import yaml; validate_startup(yaml.safe_load(open('config.yaml')))"

# Should see:
# ✅ Startup validation passed: 15/15 checks OK
```

---

## Systemd Service (Linux)

### digital-being.service

```ini
[Unit]
Description=Digital Being AI Agent
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=digital-being
WorkingDirectory=/opt/digital-being
Environment="PATH=/opt/digital-being/venv/bin"
ExecStart=/opt/digital-being/venv/bin/python main.py
Restart=always
RestartSec=10

# Graceful shutdown
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

# Resource limits
MemoryLimit=2G
CPUQuota=200%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=digital-being

[Install]
WantedBy=multi-user.target
```

### Установка

```bash
# Copy service file
sudo cp digital-being.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable digital-being

# Start service
sudo systemctl start digital-being

# Check status
sudo systemctl status digital-being

# View logs
sudo journalctl -u digital-being -f
```

---

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create volume mount points
VOLUME ["/app/memory", "/app/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s \
  CMD python -c "from core.health_check import HealthChecker; import sys; sys.exit(0 if HealthChecker().is_healthy() else 1)"

# Run
CMD ["python", "main.py"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  digital-being:
    build: .
    container_name: digital-being
    restart: unless-stopped
    
    volumes:
      - ./memory:/app/memory
      - ./logs:/app/logs
      - ./config.yaml:/app/config.yaml
    
    ports:
      - "8766:8766"
    
    environment:
      - PYTHONUNBUFFERED=1
    
    depends_on:
      - ollama
    
    networks:
      - digital-being-net
  
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    
    volumes:
      - ollama-data:/root/.ollama
    
    ports:
      - "11434:11434"
    
    networks:
      - digital-being-net

volumes:
  ollama-data:

networks:
  digital-being-net:
    driver: bridge
```

### Запуск

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f digital-being

# Stop
docker-compose down
```

---

## Monitoring Setup

### 1. Prometheus

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'digital-being'
    static_configs:
      - targets: ['localhost:8766']
    metrics_path: '/metrics'
```

### 2. Grafana Dashboards

**Import pre-built dashboards:**

1. LLM Performance
2. System Health
3. Cache Efficiency
4. Error Tracking

См. `docs/metrics-monitoring.md`

### 3. Alerts

```yaml
# alerts.yml
groups:
  - name: critical
    rules:
      - alert: HighErrorRate
        expr: rate(llm_calls_total{status="error"}[5m]) > 0.1
        for: 5m
        annotations:
          summary: "Error rate > 10%"
      
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state{name="ollama"} == 1
        for: 1m
        annotations:
          summary: "Ollama circuit breaker OPEN"
      
      - alert: ComponentUnhealthy
        expr: health_check_status == 0
        for: 2m
        annotations:
          summary: "Component {{ $labels.component }} unhealthy"
```

---

## Backup Strategy

### Что бэкапить

1. **Критичное** (ежедневно):
   - `memory/*.db` - все базы данных
   - `memory/*.lance` - vector storage
   - `config.yaml` - конфигурация

2. **Важное** (еженедельно):
   - `logs/` - логи за неделю
   - `memory/snapshots/` - снапшоты

### Backup Script

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/digital-being"
SOURCE_DIR="/opt/digital-being"

mkdir -p "$BACKUP_DIR"

# Backup databases
tar -czf "$BACKUP_DIR/memory_$DATE.tar.gz" "$SOURCE_DIR/memory"

# Backup config
cp "$SOURCE_DIR/config.yaml" "$BACKUP_DIR/config_$DATE.yaml"

# Keep only last 7 days
find "$BACKUP_DIR" -name "memory_*.tar.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "config_*.yaml" -mtime +7 -delete

echo "Backup complete: $DATE"
```

### Cron Job

```cron
# Daily backup at 3 AM
0 3 * * * /opt/digital-being/backup.sh >> /var/log/digital-being-backup.log 2>&1
```

---

## Security Hardening

### 1. Файрвол

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8766/tcp  # API (if needed externally)
sudo ufw enable
```

### 2. User Permissions

```bash
# Create dedicated user
sudo useradd -r -s /bin/false digital-being

# Set ownership
sudo chown -R digital-being:digital-being /opt/digital-being

# Restrict permissions
chmod 700 /opt/digital-being/memory
chmod 600 /opt/digital-being/config.yaml
```

### 3. API Security

```yaml
# config.yaml
api:
  enabled: true
  host: "127.0.0.1"  # Bind to localhost only
  # Use reverse proxy (nginx) for external access
```

### 4. Rate Limiting (External)

```nginx
# nginx.conf
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

server {
    location /api {
        limit_req zone=api burst=20;
        proxy_pass http://localhost:8766;
    }
}
```

---

## Performance Tuning

### 1. Cache Optimization

```yaml
# High traffic
cache:
  max_size: 500
  ttl_seconds: 300

# Low traffic
cache:
  max_size: 100
  ttl_seconds: 600
```

### 2. Rate Limiting

```yaml
# Adjust based on your Ollama capacity
rate_limit:
  chat_rate: 5.0   # Conservative
  chat_rate: 20.0  # Aggressive (if Ollama can handle)
```

### 3. Database Optimization

```python
# Periodic maintenance
# Run weekly
episodic_mem.archive_old_episodes(days=90)
vector_mem.cleanup_old_vectors(days=30)

# Vacuum databases
# Run monthly
import sqlite3
conn = sqlite3.connect("memory/episodes.db")
conn.execute("VACUUM")
conn.close()
```

---

## Troubleshooting

### Проблема: Agent не стартует

```bash
# 1. Check logs
sudo journalctl -u digital-being -n 50

# 2. Run startup validation
python -c "from core.startup_validator import validate_startup; ..."

# 3. Check Ollama
curl http://localhost:11434/api/tags

# 4. Check permissions
ls -la /opt/digital-being/memory
```

### Проблема: High memory usage

```bash
# Check cache size
curl http://localhost:8766/stats | jq '.cache'

# Reduce cache size in config.yaml
cache:
  max_size: 50

# Restart
sudo systemctl restart digital-being
```

### Проблема: Circuit breaker постоянно OPEN

```bash
# Check Ollama health
curl http://localhost:11434/api/tags

# Check Ollama logs
sudo journalctl -u ollama -n 50

# Restart Ollama
sudo systemctl restart ollama
```

---

## Scaling

### Vertical Scaling (Single Instance)

```yaml
# Increase limits
rate_limit:
  chat_rate: 50.0  # More powerful machine
  embed_rate: 100.0

cache:
  max_size: 1000  # More RAM available
```

### Horizontal Scaling (Multiple Instances)

```yaml
# Load balancer (nginx)
upstream digital_being {
    least_conn;
    server 127.0.0.1:8766;
    server 127.0.0.1:8767;
    server 127.0.0.1:8768;
}

server {
    location / {
        proxy_pass http://digital_being;
    }
}
```

---

## Production Checklist

☑️ **Pre-Deployment:**
- [ ] System requirements met
- [ ] All dependencies installed
- [ ] Config validated
- [ ] Startup validation passes

☑️ **Deployment:**
- [ ] Systemd service configured
- [ ] Auto-start enabled
- [ ] Logs rotating
- [ ] Firewall configured

☑️ **Monitoring:**
- [ ] Prometheus scraping
- [ ] Grafana dashboards
- [ ] Alerts configured
- [ ] On-call rotation

☑️ **Backup:**
- [ ] Backup script tested
- [ ] Cron job scheduled
- [ ] Restore procedure tested

☑️ **Security:**
- [ ] Dedicated user created
- [ ] Permissions restricted
- [ ] Firewall active
- [ ] API secured

---

## Связанные документы

- `docs/metrics-monitoring.md` - Prometheus + Grafana setup
- `docs/fault-tolerance.md` - Circuit breaker + health checks
- `core/startup_validator.py` - Startup validation
- `core/shutdown_handler.py` - Graceful shutdown

---

**Система готова к production!** 🚀
