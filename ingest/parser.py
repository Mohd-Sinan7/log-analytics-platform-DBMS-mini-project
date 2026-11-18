"""
parser.py — Compiled-regex log-line parser.

Log format:
    2026-10-26T10:15:32.123Z ERROR payments host-03 trace=ab12cd34 Message text here

Fields:
    ts        – ISO-8601 UTC timestamp
    severity  – DEBUG | INFO | WARN | ERROR | FATAL
    service   – service name (word chars + hyphens)
    host      – host name (word chars + hyphens)
    trace_id  – value after ``trace=``
    message   – remainder of the line (may contain spaces and special characters)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone


_LOG_PATTERN: re.Pattern[str] = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)"
    r"\s+(?P<severity>DEBUG|INFO|WARN|ERROR|FATAL)"
    r"\s+(?P<service>[\w-]+)"
    r"\s+(?P<host>[\w-]+)"
    r"\s+trace=(?P<trace_id>\S+)"
    r"\s+(?P<message>.+)$"
)


class ParseError(ValueError):
    """Raised when a log line cannot be parsed."""


@dataclass(slots=True)
class LogRecord:
    """Parsed, typed representation of a single log line."""

    ts: datetime
    severity: str
    service: str
    host: str
    trace_id: str | None
    message: str
    raw: str


def parse_line(raw: str) -> LogRecord:
    """Parse *raw* into a :class:`LogRecord`.

    Args:
        raw: A single log line (leading/trailing whitespace is stripped).

    Returns:
        A :class:`LogRecord` with all fields populated.

    Raises:
        ParseError: If the line does not match the expected format or is empty.
    """
    line = raw.strip()
    if not line:
        raise ParseError("Empty line")

    m = _LOG_PATTERN.match(line)
    if m is None:
        raise ParseError(f"Line does not match log format: {line!r}")

    ts_str   = m.group("ts")
    trace_id = m.group("trace_id")

    # Parse timestamp — fromisoformat doesn't accept trailing Z in Python < 3.11
    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(timezone.utc)

    return LogRecord(
        ts=ts,
        severity=m.group("severity"),
        service=m.group("service"),
        host=m.group("host"),
        trace_id=None if trace_id == "none" else trace_id,
        message=m.group("message"),
        raw=raw,
    )
