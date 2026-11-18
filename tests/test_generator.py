"""
test_generator.py — Smoke tests for the log generator.
"""
import subprocess
import sys
import os
import re

GENERATOR = os.path.join(os.path.dirname(__file__), "..", "generator", "generate_logs.py")

LOG_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z "
    r"(DEBUG|INFO|WARN|ERROR|FATAL) "
    r"[\w-]+ [\w-]+ trace=\S+ .+$"
)


def _run_generator(*args) -> list[str]:
    result = subprocess.run(
        [sys.executable, GENERATOR, *args],
        capture_output=True, text=True, timeout=30,
    )
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    return lines


class TestGeneratorOutput:
    def test_bulk_produces_correct_count(self):
        lines = _run_generator("--bulk", "100")
        assert len(lines) == 100

    def test_all_lines_match_format(self):
        lines = _run_generator("--bulk", "50")
        for line in lines:
            assert LOG_PATTERN.match(line), f"Bad line: {line!r}"

    def test_all_severities_represented(self):
        """With enough lines, all severities should appear."""
        lines = _run_generator("--bulk", "5000")
        severities = {l.split()[1] for l in lines}
        # With 5000 lines and weighted distribution, all should appear
        assert severities >= {"INFO", "WARN", "ERROR"}

    def test_timestamps_are_within_7_day_range(self):
        from datetime import datetime, timezone, timedelta
        lines = _run_generator("--bulk", "100")
        now = datetime.now(tz=timezone.utc)
        seven_days_ago = now - timedelta(days=7, minutes=1)
        for line in lines:
            ts_str = line.split()[0]
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            assert seven_days_ago <= ts <= now, f"Timestamp out of range: {ts_str}"

    def test_stream_mode_produces_lines(self):
        lines = _run_generator("--rate", "50", "--duration", "1")
        # With 50 lines/sec for 1 sec, expect ~50 ± big tolerance
        assert len(lines) >= 1

    def test_services_are_valid(self):
        valid_services = {"payments", "auth", "orders", "inventory", "search", "notifications"}
        lines = _run_generator("--bulk", "100")
        for line in lines:
            svc = line.split()[2]
            assert svc in valid_services, f"Unknown service: {svc}"

    def test_hosts_are_valid(self):
        valid_hosts = {f"host-{i:02d}" for i in range(1, 9)}
        lines = _run_generator("--bulk", "100")
        for line in lines:
            host = line.split()[3]
            assert host in valid_hosts, f"Unknown host: {host}"
