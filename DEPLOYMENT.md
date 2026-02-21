# Celery Async Architecture - Deployment Guide

## Overview

This architecture replaces synchronous Heavy Tick execution with asynchronous Celery tasks, providing:

- ✅ **Fault tolerance**: Automatic recovery from crashes
- ✅ **Adaptive timeouts**: Each step has optimal timeout (30-90s)
- ✅ **Parallel execution**: Optional steps run simultaneously
- ✅ **Auto-retry**: Failed tasks retry with exponential backoff
- ✅ **Checkpoints**: Resume from last successful step
- ✅ **Scalability**: Can run multiple workers

## Architecture

```
Heavy Tick Workflow:

[Monologue] (30s)
    ↓
[Goal Selection] (90s) ← Most complex step
    ↓
[Action] (45s)
    ↓
┌────────────────┬──────────────┬─────────────────┬─────────┐
│ Curiosity (30s)│ Beliefs (30s)│ Social (25s)    │ Meta (25s)│
└────────────────┴──────────────┴─────────────────┴─────────┘
         (All run in PARALLEL)
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Infrastructure (Docker)

```bash
# Start Redis and PostgreSQL
docker-compose up -d redis postgres

# Wait for services to be ready
sleep 5

# Initialize database
python scripts/init_db.py
```

### 3. Start Celery Worker

```bash
# Terminal 1: Start Celery worker
celery -A celery_app worker --loglevel=info --concurrency=4
```

### 4. Start Digital Being

```bash
# Terminal 2: Start main application
python main.py
```

## Manual Setup (Without Docker)

### Install Redis

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Windows:**
Download from: https://github.com/microsoftarchive/redis/releases

### Install PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql

# Create database
sudo -u postgres psql
CREATE DATABASE digital_being_db;
CREATE USER digital_being WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE digital_being_db TO digital_being;
\q
```

**macOS:**
```bash
brew install postgresql
brew services start postgresql
createdb digital_being_db
```

## Configuration

### Environment Variables

Create `.env` file:

```bash
# Redis
REDIS_URL=redis://localhost:6379/0

# PostgreSQL
DATABASE_URL=postgresql://digital_being:password@localhost:5432/digital_being_db

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Adaptive Timeouts

Edit `tasks/heavy_tick_tasks.py`:

```python
STEP_TIMEOUTS = {
    "monologue": 30,           # Adjust if needed
    "goal_selection": 90,      # Most complex
    "action": 45,
    "curiosity": 30,
    # ...
}
```

## Production Deployment

### Systemd Service

Create `/etc/systemd/system/digital-being-celery.service`:

```ini
[Unit]
Description=Digital Being Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=your_user
Group=your_group
WorkingDirectory=/path/to/digital-being
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --logfile=/var/log/digital-being/celery.log \
    --pidfile=/var/run/digital-being/celery.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable digital-being-celery
sudo systemctl start digital-being-celery
```

### Monitoring

**Check Celery status:**
```bash
celery -A celery_app inspect active
celery -A celery_app inspect stats
```

**View logs:**
```bash
tail -f /var/log/digital-being/celery.log
```

**Monitor tasks:**
```bash
# Install Flower (Celery monitoring tool)
pip install flower
celery -A celery_app flower --port=5555

# Open http://localhost:5555 in browser
```

## Troubleshooting

### Task Timeout Issues

If tasks still timeout, increase limits in `celery_app.py`:

```python
app.conf.update(
    task_time_limit=180,      # Hard limit: 3 minutes
    task_soft_time_limit=150, # Soft limit: 2.5 minutes
)
```

### Database Connection Errors

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
psql -U digital_being -d digital_being_db -h localhost
```

### Redis Connection Errors

```bash
# Check Redis status
redis-cli ping  # Should return PONG

# Check Redis logs
sudo journalctl -u redis
```

### View Checkpoints

```python
from database.models import WorkflowCheckpoint, SessionLocal

db = SessionLocal()
checkpoints = db.query(WorkflowCheckpoint).order_by(
    WorkflowCheckpoint.created_at.desc()
).limit(10).all()

for cp in checkpoints:
    print(f"{cp.workflow_id} - {cp.stage} - {cp.created_at}")
```

## Performance Tuning

### Increase Worker Concurrency

```bash
# More parallel tasks (uses more CPU/RAM)
celery -A celery_app worker --concurrency=8
```

### Enable Result Compression

```python
# celery_app.py
app.conf.update(
    result_compression='gzip',
    task_compression='gzip',
)
```

### Use Multiple Queues

```python
# Separate critical and optional tasks
app.conf.task_routes = {
    'heavy_tick.monologue': {'queue': 'critical'},
    'heavy_tick.goal_selection': {'queue': 'critical'},
    'heavy_tick.curiosity': {'queue': 'optional'},
}
```

## Migration from Old System

1. **Backup current state:**
   ```bash
   cp -r data/ data_backup/
   ```

2. **Update `core/heavy_tick.py`:**
   Replace synchronous execution with orchestrator:
   ```python
   from core.orchestrator import orchestrator
   
   async def heavy_tick(n: int):
       result = await orchestrator.execute_heavy_tick(n, context)
       return result
   ```

3. **Test in parallel:**
   Run old and new systems side-by-side for 24 hours

4. **Switch over:**
   Deploy new version when confident

## Benefits

| Feature | Old System | New System |
|---------|-----------|------------|
| Timeout handling | Fixed 20s per step | Adaptive 30-90s |
| Recovery | None | Automatic from checkpoint |
| Parallelism | Sequential | Optional steps parallel |
| Retry | Manual | Automatic with backoff |
| Scalability | Single process | Multiple workers |
| Monitoring | Logs only | Flower + DB tracking |

## Support

If issues persist, check:
1. Logs: `tail -f logs/digital_being.log`
2. Celery status: `celery -A celery_app inspect active`
3. Database checkpoints: Query `workflow_checkpoints` table
4. Redis queue: `redis-cli LLEN celery` (should be low)