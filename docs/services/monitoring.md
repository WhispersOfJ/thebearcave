# Monitoring Stack

Seven containers that keep the stack observable: metrics (Prometheus + exporters) and
logs (Loki + Promtail), visualized in Grafana.

---

## Prometheus

| | |
|---|---|
| **Image** | `prom/prometheus:latest` |
| **Port** | 9090 |
| **Healthcheck** | `wget --spider http://localhost:9090/-/healthy` |
| **Config** | `services/prometheus/prometheus.yml` |
| **Data** | `data/prometheus/` (30d / 2 GB retention) |

### Scrape targets

| Target | Address | Notes |
|--------|---------|-------|
| Prometheus self | `localhost:9090` | |
| Metacache | `metacache:8765/metrics/prometheus` | |
| nzbdav-exporter | `nzbdav-exporter:9200` | |
| node-exporter | `host.docker.internal:9100` | host network, via extra_hosts |
| cAdvisor | `cadvisor:8080` | |

> **Linux-only constraint:** `host.docker.internal` maps to the bridge gateway via
> `extra_hosts`. This does not resolve the same way on Docker Desktop for Mac/Windows.

---

## Loki + Promtail

| | |
|---|---|
| **Loki image** | `grafana/loki:3.7.6`, port 3100, data `data/loki/` |
| **Promtail image** | `grafana/promtail:3.6.11` |
| **Configs** | `services/loki/loki-config.yaml`, `services/promtail/promtail-config.yaml` |
| **Healthcheck** | Loki: binary `-version` probe (no shell in the image) |

- Promtail tails `/var/lib/docker/containers/*/*-json.log` and pushes to Loki
- Loki 3.x uses the TSDB schema (v13); old 2.x chunks are not migrated
- Grafana queries Loki via the provisioned datasource

---

## Grafana

| | |
|---|---|
| **Image** | `grafana/grafana:13.2.0` |
| **Port** | 3001 (host) → 3000 |
| **Healthcheck** | `wget --spider http://localhost:3000/api/health` |
| **Provisioning** | `services/grafana/provisioning/` (datasources, dashboards, alerts) |
| **Dashboards** | `services/grafana/dashboards/` |
| **Data** | `data/grafana/` |

### Provisioned dashboards

| Dashboard | What it shows |
|-----------|---------------|
| `host-metrics.json` | node-exporter host CPU/RAM/disk |
| `container-metrics.json` | cAdvisor per-container metrics |
| `nzbdav-streaming.json` | InfiniDysk queue/stream metrics |
| `loki-logs-overview.json` | Log volume, errors by container |
| `loki-import-pipeline.json` | Import pipeline log analysis |
| `stage-4-cve-tracking.json` | Trivy CVE baseline tracking |

### Alerts

- Provisioned contact point → `DISCORD_WEBHOOK_URL`
- Alert rules fire through Grafana Unified Alerting
- Metacache ships its own alert rules (`archive/metacacharr/monitoring/metacache-alerts.yml`)

### Environment variables

| Variable | Purpose |
|----------|---------|
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | Admin login |
| `DISCORD_WEBHOOK_URL` | Alert notifications |

---

## Node Exporter + cAdvisor

| | |
|---|---|
| **node-exporter** | port 9100, **host network** (needs host PID/net/uts namespaces) |
| **cAdvisor** | port 8080, `privileged: true`, `/dev/kmsg` |

- node-exporter excludes veth interfaces and mounts under `/sys|proc|dev|host|etc`
- cAdvisor binds host port **8080** — ensure nothing else uses it

---

## nzbdav-exporter

Custom Python exporter scraping InfiniDysk's SABnzbd-compatible API.

| | |
|---|---|
| **Source** | `services/nzbdav-exporter/` |
| **Port** | 9200 |
| **Healthcheck** | `urllib.request.urlopen('http://localhost:9200/healthz')` |
| **Depends on** | `nzbdav` healthy |

| Variable | Purpose |
|----------|---------|
| `NZBDAV_URL` | `http://nzbdav:3000` |
| `NZBDAV_API_KEY` | `FRONTEND_BACKEND_API_KEY` |
| `SCRAPE_INTERVAL` | 15 s |

---

## Querying

```bash
# Prometheus targets
curl http://HOST_IP:9090/api/v1/targets

# Loki log query (last hour, control-panel container)
curl -G http://HOST_IP:3100/loki/api/v1/query_range \
  --data-urlencode 'query={container="control-panel"}' \
  --data-urlencode 'start=1h'

# Grafana health
curl http://HOST_IP:3001/api/health
```

## Troubleshooting

- **Prometheus shows down targets** — check each exporter is up and on the same network;
  node-exporter is reached via the host gateway
- **No logs in Loki** — Promtail needs docker.sock + `/var/lib/docker/containers`;
  restart promtail after Docker storage changes
- **Grafana blank datasources** — provisioning is bind-mounted read-only from
  `services/grafana/provisioning/`; confirm the files parse
- **Disk filling** — Prometheus is capped at 2 GB; Loki chunks live in `data/loki/`
