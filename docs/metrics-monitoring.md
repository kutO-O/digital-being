# Metrics & Monitoring

Полное руководство по Prometheus + Grafana мониторингу.

---

## Обзор

Система собирает **40+ метрик** по 5 категориям:

1. **LLM метрики** - латенси, throughput, ошибки
2. **Cache метрики** - hit rate, evictions, size
3. **Circuit Breaker** - состояние, failures, recoveries
4. **Rate Limiter** - accepted/rejected, available tokens
5. **System Health** - здоровье компонентов, memory usage

---

## Quick Start

### 1. Установка

```bash
# Install prometheus_client
pip install prometheus-client

# Metrics теперь доступны на /metrics
# Ничего больше не нужно - всё уже работает!
```

### 2. Проверка

```bash
# Start your agent
python main.py

# Check metrics endpoint (if API enabled)
curl http://localhost:8766/metrics

# You should see Prometheus format output:
# llm_calls_total{model="llama3.2",operation="chat",status="success"} 42
# cache_hits_total{cache_type="llm"} 15
```

---

## Доступные метрики

### LLM Metrics

```prometheus
# Total calls (counter)
llm_calls_total{model, operation, status}
  - model: llama3.2, nomic-embed-text
  - operation: chat, embed
  - status: success, error, cached

# Call latency (histogram)
llm_call_duration_seconds{model, operation}
  - Buckets: 0.1s, 0.5s, 1s, 2s, 5s, 10s, 30s, 60s

# Token usage (counter)
llm_tokens_used_total{model, type}
  - type: input, output
```

### Cache Metrics

```prometheus
# Hits/misses (counters)
cache_hits_total{cache_type}
cache_misses_total{cache_type}
  - cache_type: llm, vector, other

# Current size (gauge)
cache_size_entries{cache_type}

# Evictions (counter)
cache_evictions_total{cache_type, reason}
  - reason: lru, ttl, manual
```

### Circuit Breaker Metrics

```prometheus
# State (gauge: 0=closed, 1=open, 2=half_open)
circuit_breaker_state{name}

# Counters
circuit_breaker_failures_total{name}
circuit_breaker_successes_total{name}
```

### Rate Limiter Metrics

```prometheus
# Requests (counter)
rate_limit_requests_total{limiter, status}
  - status: accepted, rejected

# Available tokens (gauge)
rate_limit_available_tokens{limiter}
```

### System Health Metrics

```prometheus
# Component health (gauge: 1=healthy, 0=unhealthy)
health_check_status{component}
  - component: ollama, episodic_memory, vector_memory, event_bus, circuit_breakers

# Errors (counter)
errors_total{component, error_type}

# Memory usage (gauge)
memory_usage_bytes{type}
db_size_bytes{db_name}
```

### Tick Metrics

```prometheus
# Duration (histogram)
tick_duration_seconds{tick_type}
  - tick_type: light, heavy

# Count (counter)
ticks_total{tick_type}
```

---

## Prometheus Setup

### prometheus.yml

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'digital-being'
    static_configs:
      - targets: ['localhost:8766']
    metrics_path: '/metrics'
```

### Запуск

```bash
# Download Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-2.45.0.linux-amd64.tar.gz
cd prometheus-2.45.0.linux-amd64

# Start
./prometheus --config.file=prometheus.yml

# Open http://localhost:9090
```

---

## Grafana Setup

### Установка

```bash
# Ubuntu/Debian
sudo apt-get install -y grafana
sudo systemctl start grafana-server

# Docker
docker run -d -p 3000:3000 grafana/grafana

# Open http://localhost:3000
# Default login: admin/admin
```

### Add Prometheus Data Source

1. Settings → Data Sources → Add data source
2. Select Prometheus
3. URL: `http://localhost:9090`
4. Save & Test

---

## Dashboard Examples

### LLM Performance Dashboard

**Panels:**

1. **Call Rate** (Graph)
```promql
rate(llm_calls_total[5m])
```

2. **Latency P95** (Graph)
```promql
histogram_quantile(0.95, rate(llm_call_duration_seconds_bucket[5m]))
```

3. **Cache Hit Rate** (Gauge)
```promql
rate(cache_hits_total[5m]) / 
(rate(cache_hits_total[5m]) + rate(cache_misses_total[5m])) * 100
```

4. **Error Rate** (Graph)
```promql
rate(llm_calls_total{status="error"}[5m])
```

### System Health Dashboard

**Panels:**

1. **Component Health** (Status)
```promql
health_check_status
```

2. **Circuit Breaker States** (Graph)
```promql
circuit_breaker_state
```

3. **Memory Usage** (Graph)
```promql
memory_usage_bytes
```

4. **Rate Limiter** (Graph)
```promql
rate_limit_available_tokens
```

---

## Alert Rules

### alerts.yml

```yaml
groups:
  - name: digital_being_alerts
    interval: 30s
    rules:
      # High error rate
      - alert: HighLLMErrorRate
        expr: |
          rate(llm_calls_total{status="error"}[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High LLM error rate"
          description: "Error rate is {{ $value }} req/s"
      
      # Circuit breaker open
      - alert: CircuitBreakerOpen
        expr: |
          circuit_breaker_state{name="ollama"} == 1
        for: 1m
        annotations:
          summary: "Circuit breaker OPEN for {{ $labels.name }}"
      
      # Low cache hit rate
      - alert: LowCacheHitRate
        expr: |
          rate(cache_hits_total[10m]) / 
          (rate(cache_hits_total[10m]) + rate(cache_misses_total[10m])) < 0.2
        for: 10m
        annotations:
          summary: "Cache hit rate below 20%"
      
      # Component unhealthy
      - alert: ComponentUnhealthy
        expr: |
          health_check_status == 0
        for: 2m
        annotations:
          summary: "Component {{ $labels.component }} unhealthy"
      
      # High latency
      - alert: HighLLMLatency
        expr: |
          histogram_quantile(0.95, 
            rate(llm_call_duration_seconds_bucket[5m])
          ) > 10
        for: 5m
        annotations:
          summary: "P95 latency above 10s"
```

---

## Полезные Queries

### Performance Analysis

```promql
# Average latency by operation
avg(rate(llm_call_duration_seconds_sum[5m])) by (operation)

# Request throughput
sum(rate(llm_calls_total[1m])) by (model)

# Cache effectiveness
100 * sum(rate(cache_hits_total[5m])) / 
(sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))

# Error percentage
100 * sum(rate(llm_calls_total{status="error"}[5m])) / 
sum(rate(llm_calls_total[5m]))
```

### Capacity Planning

```promql
# Peak request rate (last 24h)
max_over_time(rate(llm_calls_total[5m])[24h])

# 95th percentile latency
histogram_quantile(0.95, rate(llm_call_duration_seconds_bucket[1h]))

# Memory growth rate
deriv(memory_usage_bytes[1h])
```

---

## Best Practices

### 1. Что мониторить

✅ **Критичное:**
- LLM latency (P95, P99)
- Error rate
- Circuit breaker state
- Component health

✅ **Важное:**
- Cache hit rate
- Rate limiter rejections
- Memory usage
- Throughput

✅ **Полезное:**
- Tick duration
- DB size growth
- Token usage

### 2. Alert Thresholds

```yaml
# Conservative (production)
Error rate: > 5% for 5min
Latency P95: > 10s for 5min
Cache hit rate: < 20% for 10min

# Aggressive (testing)
Error rate: > 1% for 2min
Latency P95: > 5s for 2min
Cache hit rate: < 30% for 5min
```

### 3. Retention

```yaml
# Prometheus storage
Raw metrics: 15 days
Aggregated (5m): 90 days
Aggregated (1h): 1 year
```

---

## Troubleshooting

### Metrics не собираются

**Проблема:** `prometheus_client not installed`

```bash
pip install prometheus-client
```

**Проблема:** `/metrics endpoint недоступен`

Проверьте `config.yaml`:
```yaml
api:
  enabled: true
  port: 8766
```

### Grafana не показывает данные

1. Проверьте Prometheus:
```bash
curl http://localhost:9090/api/v1/targets
# Должен быть state: "up"
```

2. Проверьте queries:
```promql
llm_calls_total
# Должно вернуть данные
```

### Высокая cardinality

**Проблема:** Слишком много unique label combinations

**Решение:** Не используйте:
- User IDs в labels
- Timestamps
- Random strings
- High-cardinality dimensions

---

## Production Checklist

☑️ **Setup:**
- [ ] `prometheus-client` установлен
- [ ] API endpoint доступен
- [ ] Prometheus scraping работает
- [ ] Grafana dashboards созданы

☑️ **Monitoring:**
- [ ] Alerts настроены
- [ ] Notification channels подключены (Slack, email)
- [ ] On-call rotation организован

☑️ **Retention:**
- [ ] Prometheus storage настроен
- [ ] Backup strategy есть
- [ ] Archive старых метрик

---

## Связанные файлы

- `core/metrics.py` - Metrics collector
- `core/ollama_client.py` - Metrics integration
- `docs/fault-tolerance.md` - Circuit breaker docs
- `docs/audits/phase-1-complete-audit.md` - Full audit

## Issue Resolved

- ✅ TD-013 (P1): Metrics system
