# Log Analytics Platform

A high-performance, self-hosted, SQL-first log analytics and telemetry platform — a hybrid take on what tools like Splunk, Datadog, or the ELK stack do.

Built with **PostgreSQL 16 (Declarative Range Partitioning by Timestamp)**, **Elasticsearch 8.13 (Inverted Full-Text Index)**, **FastAPI (REST Query Engine)**, **Next.js 14 (Modern UI)**, and **Grafana 10.4 (Time-Series Monitoring)**.

---

## Architecture Overview

```
                          [ Raw Log File / Applications ]
                                         │
                                         ▼
                      [ Ingestion Agent: Python + Watchdog ]
                         (Regex parser, dead-letter quarantine)
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │ (Binary COPY @ 33k rows/sec)                  │ (Bulk Indexing)
                 ▼                                               ▼
     [ PostgreSQL 16 Relational Core ]               [ Elasticsearch 8.13 NoSQL ]
     • Range Partitioned by Timestamp                • Inverted Index on 'message'
     • 15+ Daily Partitions (Pruning Active)         • Typo-tolerant Fuzzy Search
     • B-Tree Composite & BRIN Indexes               • Linked by UUID: doc_id
     • Continuous Rollups: log_counts_minute                     │
     • RBAC: log_admin / log_analyst                             │
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         ▼
                            [ FastAPI Backend Service ]
                         (Port 8080: Keyset Pagination, JWT Auth)
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
    [ Next.js 14 Web Application ]                 [ Grafana 10.4 Dashboards ]
       (Port 3001: Interactive UI)                     (Port 3000: Operational)
    • Live SVG Time-Series Chart                   • Logs per Minute by Severity
    • Full-Text + SQL Log Explorer                 • Error Rate per Service
    • Advanced SQL Query Lab (CTEs, Joins)         • Top 10 Noisy Hosts
    • NoSQL Elasticsearch CRUD (RUD)               • Severity Distribution
    • Live Anomaly Injection & Detection           • Recent Anomaly Table
    • Admin Stored Procedures & Audit Triggers     • Real-Time Error Logs Feed
```

---

## Core Database Engineering Highlights

1. **Declarative Range Partitioning by Timestamp (`RANGE (ts)`):**
   Logs are distributed across daily physical tables (`logs_2026_11_10`, `logs_2026_11_11`, etc.). Time-filtered queries automatically leverage **Partition Pruning** to bypass irrelevant partitions (`Subplans Removed: 14`), reducing scan time from seconds to ~27 ms on 1,000,000+ rows.
2. **Hybrid Indexing Strategy (B-Tree + BRIN):**
   - **B-Tree Composite Indexes:** On `(service, ts DESC)` and `(severity, ts DESC)` for point seeks and index-only range scans.
   - **BRIN (Block Range Index):** On `ts` with `pages_per_range = 32`. Stores min/max summaries per disk block, consuming **99% less memory and disk space** than traditional B-Trees on chronological time-series data.
3. **Polyglot Persistence (Relational ACID + Inverted Index):**
   PostgreSQL enforces relational schema, rollups, and transactions, while Elasticsearch provides sub-second tokenized phrase matching and typo-tolerant fuzzy search where standard SQL `LIKE '%pattern%'` would degrade to expensive table scans. Linked via shared UUID (`doc_id`).
4. **Statistical Anomaly Detection Engine ($Z$-Score):**
   A background daemon computes a rolling 60-minute baseline (mean $\mu$, stddev $\sigma$). Spikes exceeding $Z = \frac{x - \mu}{\sigma} > 3.0$ are written to `anomalies`.
5. **Database Triggers & Stored Procedures:**
   - **Stored Procedure:** `pr_create_daily_partition(target_date)` dynamically creates new daily partition tables with constraints.
   - **Database Trigger:** `trg_audit_anomaly` intercepts inserts into `anomalies` and logs a JSON audit trail to `audit_log`.
6. **Database Role-Based Access Control (RBAC):**
   - `log_admin`: Full DDL/DML, sequence control, and stored procedure execution.
   - `log_analyst`: Read-only `SELECT` on telemetry views and dimensions; blocked from user credentials and quarantine tables.

---

## Services & Ports

| Service | Port / URL | Description | Credentials (if applicable) |
| :--- | :--- | :--- | :--- |
| **Next.js Web App** | `http://localhost:3001` | Interactive Dashboard, Log Explorer, SQL Lab & Anomaly Simulator | 1-Click Login (`admin` or `analyst`) |
| **Grafana Dashboard** | `http://localhost:3000` | 6 Provisioned Operational Telemetry Panels | `admin` / `admin` |
| **FastAPI REST API** | `http://localhost:8080` | High-speed ASGI query service & OpenAPI Docs | Swagger UI at `/docs` |
| **PostgreSQL 16** | `localhost:5432` | Partitioned Relational Database | `logs` / `logspassword` (DB: `logs`) |
| **Elasticsearch 8.13** | `http://localhost:9200` | NoSQL Inverted Index Cluster | Single-node (Security disabled locally) |

---

## How to Run (Quick Start)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running on your host)
- [Node.js](https://nodejs.org/) (v18+ or v20+)
- Python 3.11+ (optional, for local unit tests)

---

### Step 1: Start the Backend & Database Stack

Open terminal in the project directory:

```bash
cd "log-analytics"

# 1. Copy environment configuration
cp .env.example .env

# 2. Launch Docker Compose containers
docker compose up -d
```

Verify that all containers are healthy:
```bash
docker compose ps
```
You should see `log_postgres`, `log_elasticsearch`, `log_api`, `log_grafana`, `log_ingest`, and `log_anomaly` running.

---

### Step 2: Seed Sample Log Data (100,000+ Logs)

Generate a bulk synthetic dataset spread across the last 7 days:

```bash
docker compose run --rm generator --bulk 100000 --out /var/log/app/app.log
```

The `ingest` agent will automatically detect the file, parse the records with regex, and stream them into PostgreSQL and Elasticsearch via binary `COPY` at >30,000 rows/sec.

---

### Step 3: Start the Next.js Web Application

In a new terminal window:

```bash
cd web
npm install
npm start
```

Open your browser to:
**[http://localhost:3001](http://localhost:3001)**

---

## Live Demo Walkthrough (How to Demonstrate)

Follow this 5-minute walkthrough to demonstrate all capabilities:

### 1. Authentication & Role-Based Access Control (RBAC)
- In the top-right header of `http://localhost:3001`, click **"Login as Analyst"** (Blue badge: `ROLE: analyst`).
  - Explain: *The analyst has read-only access to search logs and view telemetry. The "Admin Controls" tab is hidden.*
- Click **"Login as Admin"** (Purple badge: `ROLE: admin`).
  - Explain: *The admin role unlocks partition maintenance stored procedures and audit logs.*

### 2. Live Anomaly Injection & Detection Demo
- On the **Dashboard Overview** or **Anomaly Engine** tab, locate the **"Live Anomaly Injection & Detection Demo"** widget.
- Select target service: `payments`, Error Spike: `1500`, and click **"Inject Live Spike & Detect"**.
- **Observe what happens in real time:**
  1. A red banner flashes: `🚨 ANOMALY DETECTED LIVE: Injected 1500 errors into service 'payments'. Z-Score: 2995.00 > 3.0 threshold. Database trigger executed!`
  2. The **Real-Time Time-Series Graph** immediately redraws with a sharp red peak and yellow pulsed marker.
  3. The **Anomaly Engine** table logs the new anomaly with timestamp and computed $Z$-score.
  4. The PostgreSQL database trigger `trg_audit_anomaly` writes an entry to `audit_log`.
  5. In Grafana (`http://localhost:3000`), the "Error Rate per Service" graph shoots up!

### 3. Log Explorer (Hybrid SQL + Elasticsearch Search)
- Switch to the **Log Explorer** tab.
- Type a search query like `timeout` or `circuit breaker` and hit Enter — executes full-text search against Elasticsearch.
- Filter by Severity (`ERROR`) or Service (`payments`) — executed against PostgreSQL composite B-Tree indexes.

### 4. Advanced SQL Lab
- Click the **Advanced SQL Lab** tab.
- Run any of the 5 relational query patterns:
  - **1. Join Query:** 4-table join (`logs` + `services_dim` + `hosts_dim` + `anomalies`).
  - **2. Nested Subquery:** Filter logs for high-risk anomaly services (`WHERE service IN (SELECT ...)`).
  - **3. Correlated Subquery:** Compare each service against the average error count of its own tier.
  - **4. Recursive CTE (`WITH RECURSIVE`):** Continuous 10-minute interval generator.
  - **5. Window Analytical CTE:** Calculates error velocity using `LAG()`, moving averages, and `RANK()`.
- Inspect the formatted SQL query, PostgreSQL `EXPLAIN ANALYZE` execution plan, and the resulting records table.

### 5. NoSQL (Elasticsearch CRUD)
- Go to the **NoSQL (Elasticsearch)** tab.
- Click **"Create / Index Doc"** to index a document.
- Click **"Read (GET)"**, **"Update (PUT)"**, or **"Delete (DEL)"** using the auto-populated `_id`.

### 6. Admin Controls & Database Trigger Verification
- Go to the **Admin Controls** tab (logged in as Admin).
- Pick a date (e.g. `2026-11-25`) and click **"Call Procedure"** — executes stored procedure `pr_create_daily_partition`.
- Scroll to the **Database Audit Trail** table and click **"Refresh Audit"** to view trigger-logged audit records.

---

## Running Automated Tests

Run the test suite covering parser regex, generators, database constraints, and REST API integration:

```bash
pytest -v
```

**Result:** `32 passed in 3.42s` (100% test pass rate).

---

## Running Benchmarks

```bash
# Query benchmarks (Partition pruning vs full-table scan, B-Tree vs BRIN, LIKE vs ES)
python bench/bench_queries.py --rows 100000

# Ingestion benchmarks (lines/sec)
python bench/bench_ingest.py --rows 100000
```

Results are stored in [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md).

---

## Repository Structure

```
log-analytics/
├── api/                           # FastAPI Backend Query Service (Port 8080)
│   ├── routes/
│   │   ├── advanced.py            # Executes Join, Nested, Correlated, Recursive SQL
│   │   ├── anomalies.py           # Z-Score anomaly feeds & live simulation
│   │   ├── auth.py                # JWT authentication & Role-Based Access Control
│   │   ├── health.py              # Container health checks
│   │   ├── logs.py                # Keyset-paginated PostgreSQL logs
│   │   ├── nosql.py               # Elasticsearch CRUD operations
│   │   ├── search.py              # Elasticsearch fuzzy/phrase search
│   │   └── stats.py               # Aggregation rollups
│   ├── es_client.py               # Elasticsearch async connection
│   ├── main.py                    # ASGI app entry point
│   ├── models.py                  # Pydantic schema models
│   └── queries.py                 # Parameterized SQL query helpers
├── db/                            # PostgreSQL DDL Migrations & Stored Logic
│   ├── 001_schema.sql             # Partitioned base schema & check constraints
│   ├── 002_partitions.sql         # 15 daily partitions + logs_default
│   ├── 003_indexes.sql            # BRIN index + Composite B-Trees
│   ├── 004_rollups.sql            # Continuous rollup table & refresh functions
│   ├── 005_anomalies.sql          # Anomalies table schema
│   ├── 006_auth_and_rbac.sql      # Users, audit_log, and native PG roles (RBAC)
│   └── 007_advanced_queries.sql   # Stored procedure, trigger, views, and CTEs
├── ingest/                        # High-Throughput Log Ingestion Engine
│   ├── agent.py                   # Async watchdog directory tailer
│   ├── parser.py                  # Regex parser with dead-letter isolation
│   └── writers.py                 # Asyncpg binary COPY writer (33k+ rows/s)
├── anomaly/                       # Statistical Anomaly Detection Daemon
│   └── detector.py                # Rolling 60m Z-score detector (Z > 3.0)
├── dashboards/                    # Grafana Provisioning (Port 3000)
│   ├── datasource.yml             # PostgresLogs datasource definition
│   ├── dashboards.yml             # Dashboard provider configuration
│   └── log_analytics.json         # 6 Operational monitoring panels
├── web/                           # Next.js 14 Frontend Web Application (Port 3001)
│   ├── app/
│   │   ├── globals.css            # Tailwind CSS design system
│   │   ├── layout.tsx             # Root layout & page metadata
│   │   └── page.tsx               # Main Dashboard, Log Explorer, SQL Lab, NoSQL CRUD
│   ├── package.json
│   └── tailwind.config.ts
├── docs/                          # Comprehensive Documentation
│   ├── ARCHITECTURE.md            # Mermaid system diagrams & data flow
│   ├── BENCHMARKS.md              # Performance benchmark comparisons
│   ├── DECISIONS.md               # Architecture decision records (ADRs)
│   └── PES_DBMS_PROJECT_REPORT.md # Formal 50-mark DBMS Project Report
├── docker-compose.yml             # Multi-Container Stack Orchestration
├── Makefile                       # Convenience build and run targets
├── pytest.ini                     # Pytest configuration
└── README.md                      # Project manual and execution guide
```

---

## Authors & License

Developed as a **Database Management Systems (DBMS)** project demonstrating advanced relational schema design, table partitioning, NoSQL inverted indexing, statistical telemetry analysis, and full-stack web integration.

Open-source under the [MIT License](LICENSE).
