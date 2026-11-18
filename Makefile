.PHONY: up down gen bulk spike ingest test bench logs

# Detect OS and set DOCKER command
ifeq ($(OS),Windows_NT)
  DOCKER := "C:/Users/DELL/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
else
  DOCKER := docker
endif

# ── Docker helpers ───────────────────────────────────────────────────────────
up:
	@echo "Starting all services..."
	$(DOCKER) compose up -d --build
	@echo "Services starting. Run 'make logs' to watch."

down:
	$(DOCKER) compose down -v

logs:
	$(DOCKER) compose logs -f

# ── Log generation ───────────────────────────────────────────────────────────

# Stream 20 lines/sec into the shared log volume for 120 seconds
gen:
	$(DOCKER) compose run --rm generator \
		--rate 20 --duration 120 --out /var/log/app/app.log

# Write N bulk lines (default 100k) spread over last 7 days
bulk:
	$(DOCKER) compose run --rm generator \
		--bulk $(or $(N),100000) --out /var/log/app/app.log

# Spike mode: payments service spikes with errors at t=30s for 60s
spike:
	$(DOCKER) compose run --rm generator \
		--rate 50 --duration 180 \
		--spike-service payments --spike-at 30 --spike-duration 60 \
		--out /var/log/app/app.log

# ── Ingest (backfill a local file) ──────────────────────────────────────────
ingest:
	$(DOCKER) compose exec ingest python -m ingest.agent --backfill --file /var/log/app/app.log

# ── Tests ────────────────────────────────────────────────────────────────────
test:
	python -m pytest tests/ -v

# ── Benchmarks ───────────────────────────────────────────────────────────────
bench:
	python bench/bench_queries.py --rows 100000
	python bench/bench_ingest.py  --rows 100000
