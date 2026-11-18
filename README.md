# Log Analytics Platform

A self-hosted, SQL-first log analytics platform — a mini Splunk/ELK stack.

```
Logs → Ingest Agent → PostgreSQL (structured) + Elasticsearch (full-text)
                   ↓
            FastAPI REST API ← Grafana dashboards
                   ↓
          Anomaly Detector (z-score)
```

## Prerequisites

| Tool | Version |
|------|---------|
| Docker Desktop | ≥ 25.x |
| Docker Compose | v2 (bundled with Desktop) |
| Python | 3.11+ (only needed for local tests/bench) |
| GNU Make | optional (PowerShell equivalents below) |

## Quick Start

```bash
# 1. Clone / enter the repo
cd "log-analytics"

# 2. Copy env (edit passwords if desired)
cp .env.example .env

# 3. Start everything
docker compose up -d --build

# 4. Wait for all services to become healthy (~60s on first run)
docker compose ps

# 5. Seed data — generate 100k lines spread over last 7 days
docker compose run --rm generator --bulk 100000 --out /var/log/app/app.log

# 6. Watch the ingest container pick them up
docker compose logs -f ingest
```

## Services & Ports

| Service | URL |
|---------|-----|
| API (FastAPI) | http://localhost:8080 |
| API Docs | http://localhost:8080/docs |
| Grafana | http://localhost:3000 (admin/admin) |
| Postgres | localhost:5432 |
| Elasticsearch | http://localhost:9200 |

## API Examples

```bash
# Health check
curl http://localhost:8080/health

# List latest 20 ERROR logs
curl "http://localhost:8080/logs?severity=ERROR&limit=20"

# Paginated — use next_cursor from previous response
curl "http://localhost:8080/logs?severity=ERROR&limit=20&cursor=<token>"

# Trace all logs for a trace ID
curl "http://localhost:8080/trace/ab12cd34"

# Full-text search (Elasticsearch)
curl "http://localhost:8080/search?q=timeout"

# Fuzzy search
curl "http://localhost:8080/search?q=timout&fuzzy=true"

# Error rate per minute for payments service (last hour)
curl "http://localhost:8080/stats/error-rate?service=payments&interval=1m"

# Top noisy hosts
curl "http://localhost:8080/stats/top-hosts?severity=ERROR"

# Anomalies
curl "http://localhost:8080/anomalies"
```

## Demo Script

```bash
# Terminal 1 — watch ingest in real time
docker compose logs -f ingest

# Terminal 2 — generate a spike in the payments service
docker compose run --rm generator \
  --rate 50 --duration 180 \
  --spike-service payments --spike-at 30 --spike-duration 60 \
  --out /var/log/app/app.log

# Terminal 3 — poll anomalies (anomaly appears within ~2 minutes)
watch -n 5 "curl -s http://localhost:8080/anomalies | python -m json.tool"

# Open Grafana → http://localhost:3000
# Dashboard: "Log Analytics Overview"
```

## Running Tests

```bash
pip install pytest fastapi httpx asyncpg elasticsearch pydantic watchdog
python -m pytest tests/ -v
```

## Running Benchmarks

```bash
# Requires the stack to be running
python bench/bench_queries.py --rows 100000
python bench/bench_ingest.py  --rows 100000
```

Results are written to `docs/BENCHMARKS.md`.

## Backfill Mode

```bash
# Generate a large file locally
python generator/generate_logs.py --bulk 1000000 --out /tmp/big.log

# Ingest as fast as possible
docker compose exec ingest python -m ingest.agent --backfill --file /tmp/big.log
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| ES container exits (OOM) | Increase Docker memory to ≥ 4 GB in Docker Desktop settings |
| `pg_isready` fails | Wait 20s; Postgres takes time to init partitions on first start |
| Grafana shows "no data" | Run `make bulk` or `make gen` to seed data |
| Ingest shows 0 writes | Check `LOG_FILE` in `.env` matches the generator output path |
| API returns 500 on `/search` | ES index not yet created; wait for ingest to start |

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full Mermaid diagram,
ER diagram, and design decisions.

## Decisions

See [docs/DECISIONS.md](docs/DECISIONS.md) for all design decisions with rationale.
