# 🚀 Agent Autoscaling

## Overview

Agent Autoscaling automatically manages the number of agents in your multi-agent system based on workload. It monitors agent performance and:

- **Scales UP** when agents are overloaded (>75% load)
- **Scales DOWN** when agents are underutilized (<25% load)
- **Replaces unhealthy** agents that stop responding

## Quick Start

### 1. Enable Autoscaling

Edit `config.yaml`:

```yaml
multi_agent:
  enabled: true  # Must be enabled first
  autoscaling:
    enabled: true  # ✅ Enable autoscaling
```

### 2. Run the System

```bash
python main.py
```

### 3. Monitor Scaling Events

Visit http://127.0.0.1:8766 and check:
- **Agent Stats** - Current agent count and load
- **Scaling Events** - Recent scale-up/down events

---

## Configuration

### Scaling Thresholds

```yaml
autoscaling:
  scale_up_threshold: 0.75    # Scale up when avg load > 75%
  scale_down_threshold: 0.25  # Scale down when avg load < 25%
```

**Example:**
- 3 researcher agents with loads: 0.8, 0.85, 0.9
- Average load = 0.85 (85%)
- 85% > 75% ➡️ **Scale UP** ➕ Add new researcher agent

### Cooldown Periods

Prevent rapid scaling oscillations:

```yaml
autoscaling:
  scale_up_cooldown_sec: 300    # Wait 5 min between scale-ups
  scale_down_cooldown_sec: 600  # Wait 10 min between scale-downs
```

### Agent Limits

```yaml
autoscaling:
  min_agents_per_type: 1  # Always keep at least 1
  max_agents_per_type: 5  # Never exceed 5 per specialization
```

### Health Monitoring

```yaml
autoscaling:
  unhealthy_threshold: 3       # Failed heartbeats before replacement
  heartbeat_timeout_sec: 120   # 2 min without heartbeat = unhealthy
```

---

## How It Works

### 1. Load Monitoring

Every `check_interval_sec` (default 60s), the autoscaler:

1. Reads agent load from registry
2. Calculates average load per specialization
3. Compares against thresholds

### 2. Scaling Decisions

#### Scale UP (Add Agent)
```
IF avg_load > scale_up_threshold
AND count < max_agents_per_type
AND cooldown_elapsed
THEN create_new_agent()
```

#### Scale DOWN (Remove Agent)
```
IF avg_load < scale_down_threshold
AND count > min_agents_per_type
AND cooldown_elapsed
THEN remove_least_loaded_agent()
```

#### Replace Unhealthy
```
IF agent.missed_heartbeats >= unhealthy_threshold
THEN replace_agent()
```

### 3. Port Allocation

New agents get assigned ports from configured ranges:

```yaml
port_ranges:
  research: [9101, 9150]    # Up to 50 research agents
  execution: [9201, 9250]   # Up to 50 execution agents
  # ...
```

---

## Examples

### Example 1: Research Workload Spike

**Initial State:**
```
researcher_1: load=0.3
researcher_2: load=0.4
Avg load = 0.35 (35%)
```

**Heavy workload arrives:**
```
researcher_1: load=0.9
researcher_2: load=0.85
Avg load = 0.875 (87.5%)
```

**Autoscaler Action:**
```
87.5% > 75% threshold
✅ Scale UP: Create researcher_3 on port 9101
```

**New State:**
```
researcher_1: load=0.6
researcher_2: load=0.55
researcher_3: load=0.5
Avg load = 0.55 (55%)
```

### Example 2: Workload Decreases

**Initial State:**
```
executor_1: load=0.1
executor_2: load=0.15
executor_3: load=0.05
Avg load = 0.1 (10%)
```

**Autoscaler Action:**
```
10% < 25% threshold
Wait 10 min cooldown...
✅ Scale DOWN: Remove executor_3 (lowest load)
```

**New State:**
```
executor_1: load=0.15
executor_2: load=0.15
Avg load = 0.15 (15%)
```

### Example 3: Unhealthy Agent Replacement

**Problem:**
```
analyst_2 stopped responding
Missed heartbeats: 3 (>= threshold)
```

**Autoscaler Action:**
```
❌ analyst_2 is unhealthy
✅ Replace: Create analyst_4 on port 9302
🗑️ Remove: analyst_2
```

---

## API Endpoints

### Get Scaling Stats

```bash
curl http://127.0.0.1:8766/autoscaler/stats
```

**Response:**
```json
{
  "policy": {
    "scale_up_threshold": 0.75,
    "scale_down_threshold": 0.25,
    "min_agents_per_type": 1,
    "max_agents_per_type": 5
  },
  "specializations": {
    "research": {
      "count": 2,
      "avg_load": 0.45
    },
    "execution": {
      "count": 1,
      "avg_load": 0.3
    }
  },
  "scaling_events": 5,
  "unhealthy_agents": 0
}
```

### Get Recent Events

```bash
curl http://127.0.0.1:8766/autoscaler/events?limit=10
```

**Response:**
```json
{
  "events": [
    {
      "timestamp": 1708612345.67,
      "type": "scale_up",
      "specialization": "research",
      "reason": "High load: 0.87 > 0.75",
      "agent_id": "researcher_3"
    },
    {
      "timestamp": 1708609876.54,
      "type": "scale_down",
      "specialization": "execution",
      "reason": "Low load: 0.15 < 0.25",
      "agent_id": "executor_3"
    }
  ]
}
```

---

## Best Practices

### 1. Start Conservatively

```yaml
scale_up_threshold: 0.75    # Don't scale too aggressively
max_agents_per_type: 3      # Start with lower limits
```

### 2. Monitor Performance

Watch Ollama CPU/RAM usage:
- Each agent uses ~100MB RAM
- Ollama queues requests sequentially
- 5-10 agents = optimal for single Ollama instance

### 3. Use Longer Cooldowns

```yaml
scale_up_cooldown_sec: 600    # 10 min for production
scale_down_cooldown_sec: 1200 # 20 min for production
```

Prevents thrashing during load fluctuations.

### 4. Core Agents Are Protected

The 6 core agents (primary, researcher, executor, analyst, planner, tester) are **never removed** by autoscaler.

---

## Troubleshooting

### Problem: Agents Not Scaling

**Check:**
1. Is `autoscaling.enabled: true`?
2. Is `multi_agent.enabled: true`?
3. Are agents reporting load via heartbeats?
4. Is cooldown period active?

```bash
# View logs
tail -f logs/digital_being.log | grep -i "autoscaler\|scale"
```

### Problem: Too Many Agents Created

**Solution:**
```yaml
max_agents_per_type: 3  # Reduce limit
scale_up_threshold: 0.85  # Higher threshold
```

### Problem: Agents Keep Getting Removed

**Solution:**
```yaml
min_agents_per_type: 2  # Keep more agents
scale_down_threshold: 0.15  # Lower threshold
```

### Problem: Ports Exhausted

**Solution:**
```yaml
port_ranges:
  research: [9101, 9200]  # Expand range
```

---

## Performance Impact

### Scaling Check Overhead

- **CPU:** <1% (simple calculations)
- **RAM:** ~10KB per agent tracked
- **Disk:** ~1KB per scaling event

### Recommended Limits

| System | Max Agents | Notes |
|--------|-----------|-------|
| **Laptop** (16GB RAM) | 10-15 | Ollama becomes bottleneck |
| **Workstation** (32GB+) | 20-30 | Need multiple Ollama instances |
| **Server** (64GB+) | 50+ | Distributed setup recommended |

---

## Advanced: Manual Control

### Trigger Scaling Check via API

```python
import requests

# Force immediate scaling check
response = requests.post(
    "http://127.0.0.1:8766/autoscaler/check"
)
print(response.json())
```

### Temporarily Disable Autoscaling

```python
import requests

# Disable
requests.post("http://127.0.0.1:8766/autoscaler/disable")

# Enable
requests.post("http://127.0.0.1:8766/autoscaler/enable")
```

---

## Next Steps

1. **Enable autoscaling** in `config.yaml`
2. **Monitor metrics** via http://127.0.0.1:8766
3. **Tune thresholds** based on your workload
4. **Scale horizontally** with distributed agents (future)

For more advanced setups, see:
- [Multi-Agent Architecture](./MULTI_AGENT.md)
- [Distributed Setup](./DISTRIBUTED.md)
- [Performance Tuning](./PERFORMANCE.md)
