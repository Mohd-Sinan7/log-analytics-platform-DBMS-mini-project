"""
test_parser.py — Unit tests for ingest/parser.py.
"""
import pytest
from datetime import timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ingest.parser import parse_line, ParseError, LogRecord


VALID_LINE = "2026-10-26T10:15:32.123Z ERROR payments host-03 trace=ab12cd34 Payment gateway timeout after 3 retries"
VALID_NO_TRACE = "2026-10-26T10:15:32.123Z INFO auth host-01 trace=none User logged in"
MULTIWORD_MSG = "2026-10-26T10:15:32.123Z WARN orders host-02 trace=ff00ff01 Order ORD-123456 status changed to shipped"
SPECIAL_CHARS = "2026-10-26T10:15:32.123Z DEBUG search host-05 trace=aabb1234 Query 'running shoes' returned 42 results in 123ms"


class TestParseValid:
    def test_basic_error_line(self):
        rec = parse_line(VALID_LINE)
        assert rec.severity == "ERROR"
        assert rec.service == "payments"
        assert rec.host == "host-03"
        assert rec.trace_id == "ab12cd34"
        assert "Payment gateway" in rec.message
        assert rec.ts.tzinfo == timezone.utc

    def test_none_trace_becomes_null(self):
        rec = parse_line(VALID_NO_TRACE)
        assert rec.trace_id is None

    def test_multi_word_message(self):
        rec = parse_line(MULTIWORD_MSG)
        assert "status changed to shipped" in rec.message

    def test_special_characters_in_message(self):
        rec = parse_line(SPECIAL_CHARS)
        assert "'running shoes'" in rec.message

    def test_all_severities(self):
        for sev in ("DEBUG", "INFO", "WARN", "ERROR", "FATAL"):
            line = f"2026-10-26T10:15:32.123Z {sev} payments host-01 trace=abc123 test message"
            rec = parse_line(line)
            assert rec.severity == sev

    def test_raw_preserved(self):
        rec = parse_line(VALID_LINE)
        assert rec.raw == VALID_LINE

    def test_leading_trailing_whitespace_stripped(self):
        rec = parse_line("  " + VALID_LINE + "  ")
        assert rec.severity == "ERROR"

    def test_timestamp_parsed_correctly(self):
        rec = parse_line(VALID_LINE)
        assert rec.ts.year == 2026
        assert rec.ts.month == 10
        assert rec.ts.day == 26
        assert rec.ts.hour == 10
        assert rec.ts.minute == 15
        assert rec.ts.second == 32


class TestParseMalformed:
    def test_empty_line_raises(self):
        with pytest.raises(ParseError, match="Empty line"):
            parse_line("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ParseError, match="Empty line"):
            parse_line("   ")

    def test_missing_severity_raises(self):
        with pytest.raises(ParseError):
            parse_line("2026-10-26T10:15:32.123Z payments host-03 trace=ab12 msg")

    def test_invalid_severity_raises(self):
        with pytest.raises(ParseError):
            parse_line("2026-10-26T10:15:32.123Z CRITICAL payments host-03 trace=ab12 msg")

    def test_missing_trace_field_raises(self):
        with pytest.raises(ParseError):
            parse_line("2026-10-26T10:15:32.123Z ERROR payments host-03 Payment gateway timeout")

    def test_bad_timestamp_raises(self):
        with pytest.raises(ParseError):
            parse_line("NOT-A-TIMESTAMP ERROR payments host-03 trace=ab12 msg")

    def test_partial_line_raises(self):
        with pytest.raises(ParseError):
            parse_line("2026-10-26T10:15:32.123Z ERROR")
