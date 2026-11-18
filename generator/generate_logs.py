#!/usr/bin/env python3
"""
generate_logs.py — Realistic log-line generator for the Log Analytics Platform.

Usage examples:
  python generate_logs.py --rate 100 --duration 60 --out /tmp/app.log
  python generate_logs.py --bulk 1000000 --out /tmp/bulk.log
  python generate_logs.py --rate 50 --spike-service payments --spike-at 30 \
      --spike-duration 20 --duration 120 --out /tmp/app.log
"""
from __future__ import annotations

import argparse
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVICES = ["payments", "auth", "orders", "inventory", "search", "notifications"]
HOSTS = [f"host-{i:02d}" for i in range(1, 9)]

SEVERITY_WEIGHTS = {
    "INFO":  70,
    "WARN":  15,
    "ERROR": 10,
    "DEBUG":  3,
    "FATAL":  2,
}

SPIKE_SEVERITY_WEIGHTS = {
    "INFO":  20,
    "WARN":  15,
    "ERROR": 58,
    "DEBUG":  2,
    "FATAL":  5,
}

_SEVERITIES      = list(SEVERITY_WEIGHTS.keys())
_WEIGHTS         = list(SEVERITY_WEIGHTS.values())
_SPIKE_SEVERITIES = list(SPIKE_SEVERITY_WEIGHTS.keys())
_SPIKE_WEIGHTS    = list(SPIKE_SEVERITY_WEIGHTS.values())

# Message templates per service
_TEMPLATES: dict[str, list[str]] = {
    "payments": [
        "Payment gateway timeout after {n} retries",
        "Charge {amount} USD for order {order} succeeded",
        "Refund initiated for transaction {txn}",
        "Payment method validation failed: invalid CVV",
        "3DS authentication required for card ending {card}",
        "Webhook delivery failed for event {event}",
        "Currency conversion rate fetched: USD/{cur}={rate}",
        "Daily settlement batch processed {n} transactions",
    ],
    "auth": [
        "User {user} logged in from {ip}",
        "Login failed for user {user}: invalid password",
        "Token refreshed for session {sid}",
        "MFA challenge issued for user {user}",
        "Account locked after {n} failed attempts for {user}",
        "OAuth2 code exchange succeeded for client {client}",
        "JWT validation failed: token expired",
        "Password reset requested for {user}",
    ],
    "orders": [
        "Order {order} created with {n} items",
        "Order {order} status changed to {status}",
        "Inventory reservation failed for SKU {sku}",
        "Shipping label generated for order {order}",
        "Order {order} cancelled by user {user}",
        "Price recalculation triggered for cart {cart}",
        "Discount code {code} applied: {pct}% off",
        "Order {order} fulfilment delayed: warehouse backlog",
    ],
    "inventory": [
        "Stock level for SKU {sku} updated to {n}",
        "Low-stock alert for SKU {sku}: {n} remaining",
        "Reorder triggered for SKU {sku} from supplier {sup}",
        "Warehouse transfer {n} units of SKU {sku} from {wh1} to {wh2}",
        "Cycle count discrepancy for SKU {sku}: expected {n1} found {n2}",
        "SKU {sku} marked out-of-stock",
        "Bulk import completed: {n} SKUs updated",
        "Shrinkage report generated for location {loc}",
    ],
    "search": [
        "Query '{q}' returned {n} results in {ms}ms",
        "Index refresh completed: {n} documents",
        "Cache miss for query '{q}'",
        "Slow query detected ({ms}ms): '{q}'",
        "Autocomplete index rebuilt: {n} terms",
        "Spelling suggestion generated: '{q}' -> '{sugg}'",
        "Facet aggregation timeout for field {field}",
        "Search ranking model updated: version {v}",
    ],
    "notifications": [
        "Email sent to {email} for event {event}",
        "SMS delivery failed for +{phone}: carrier error",
        "Push notification delivered to device {dev}",
        "Template {tmpl} rendered in {ms}ms",
        "Notification batch {batch} queued: {n} messages",
        "Bounce received from {email}",
        "Unsubscribe processed for {email}",
        "Rate limit applied: {n} notifications deferred",
    ],
}

_FILLER: dict[str, dict[str, object]] = {
    "n":      lambda: random.randint(1, 100),
    "amount": lambda: f"{random.uniform(1, 9999):.2f}",
    "order":  lambda: f"ORD-{random.randint(100000,999999)}",
    "txn":    lambda: f"TXN-{uuid.uuid4().hex[:12].upper()}",
    "card":   lambda: f"{random.randint(1000,9999)}",
    "event":  lambda: random.choice(["charge.succeeded","refund.created","payment.failed","customer.created"]),
    "cur":    lambda: random.choice(["EUR","GBP","JPY","INR","CAD"]),
    "rate":   lambda: f"{random.uniform(0.5,150):.4f}",
    "user":   lambda: f"user_{random.randint(1000,9999)}",
    "ip":     lambda: f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
    "sid":    lambda: uuid.uuid4().hex[:16],
    "client": lambda: random.choice(["mobile-ios","mobile-android","web-spa","partner-api"]),
    "status": lambda: random.choice(["confirmed","processing","shipped","delivered","returned"]),
    "sku":    lambda: f"SKU-{random.randint(10000,99999)}",
    "cart":   lambda: f"CART-{uuid.uuid4().hex[:8]}",
    "code":   lambda: random.choice(["SUMMER20","FLASH10","LOYALTY5","WELCOME15"]),
    "pct":    lambda: random.choice([5,10,15,20,25]),
    "sup":    lambda: random.choice(["SupplierA","SupplierB","SupplierC"]),
    "wh1":    lambda: random.choice(["WH-EAST","WH-WEST","WH-NORTH"]),
    "wh2":    lambda: random.choice(["WH-SOUTH","WH-CENTRAL","WH-MAIN"]),
    "n1":     lambda: random.randint(50,500),
    "n2":     lambda: random.randint(40,490),
    "loc":    lambda: f"AISLE-{random.randint(1,20)}-SHELF-{random.randint(1,5)}",
    "q":      lambda: random.choice(["running shoes","laptop","coffee maker","wireless headphones","gaming chair"]),
    "ms":     lambda: random.randint(5,5000),
    "v":      lambda: f"{random.randint(1,5)}.{random.randint(0,9)}",
    "field":  lambda: random.choice(["brand","price","category","rating"]),
    "sugg":   lambda: random.choice(["laptops","headphones","keyboards"]),
    "email":  lambda: f"user{random.randint(1000,9999)}@example.com",
    "phone":  lambda: f"1{random.randint(2000000000,9999999999)}",
    "dev":    lambda: uuid.uuid4().hex[:16],
    "tmpl":   lambda: random.choice(["order-confirm","password-reset","promo","shipping-update"]),
    "batch":  lambda: uuid.uuid4().hex[:8],
}


def _fill(template: str) -> str:
    """Replace all {placeholder} tokens in *template* with random values."""
    import re
    def replacer(m: re.Match) -> str:
        key = m.group(1)
        fn = _FILLER.get(key)
        return str(fn()) if fn else m.group(0)
    return re.sub(r"\{(\w+)\}", replacer, template)


def make_line(
    ts: datetime,
    service: str | None = None,
    spike_service: str | None = None,
    in_spike: bool = False,
) -> str:
    """Return a single formatted log line."""
    if service is None:
        service = random.choice(SERVICES)

    if in_spike and service == spike_service:
        severity = random.choices(_SPIKE_SEVERITIES, _SPIKE_WEIGHTS)[0]
    else:
        severity = random.choices(_SEVERITIES, _WEIGHTS)[0]

    host     = random.choice(HOSTS)
    trace_id = uuid.uuid4().hex[:8] if random.random() < 0.8 else "none"
    template = random.choice(_TEMPLATES[service])
    message  = _fill(template)

    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"
    return f"{ts_str} {severity} {service} {host} trace={trace_id} {message}"


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def run_stream(
    rate: float,
    duration: float | None,
    out_path: str,
    spike_service: str | None,
    spike_at: float | None,
    spike_duration: float | None,
) -> None:
    """Tail-mode: write lines at *rate* lines/sec until *duration* elapses."""
    fh = open(out_path, "a", buffering=1) if out_path else sys.stdout  # line-buffered
    start = time.monotonic()
    count = 0
    interval = 1.0 / rate if rate > 0 else 0

    try:
        while True:
            elapsed = time.monotonic() - start
            if duration and elapsed >= duration:
                break

            in_spike = False
            if spike_service and spike_at is not None and spike_duration is not None:
                in_spike = spike_at <= elapsed < spike_at + spike_duration

            now = datetime.now(tz=timezone.utc)
            line = make_line(now, spike_service=spike_service, in_spike=in_spike)
            print(line, file=fh)
            count += 1

            if interval > 0:
                time.sleep(max(0.0, interval - (time.monotonic() - start - elapsed)))

    finally:
        if out_path:
            fh.close()
        print(f"Generated {count} lines.", file=sys.stderr)


def run_bulk(n: int, out_path: str) -> None:
    """Bulk mode: write *n* lines instantly with timestamps spread over last 7 days."""
    now = datetime.now(tz=timezone.utc)
    seven_days = timedelta(days=7)
    fh = open(out_path, "a") if out_path else sys.stdout

    batch_size = 10_000
    written = 0

    try:
        while written < n:
            chunk = min(batch_size, n - written)
            lines = []
            for _ in range(chunk):
                delta = timedelta(seconds=random.uniform(0, seven_days.total_seconds()))
                ts = now - seven_days + delta
                lines.append(make_line(ts))
            fh.write("\n".join(lines) + "\n")
            written += chunk
            if written % 100_000 == 0:
                print(f"  ... {written}/{n} lines written", file=sys.stderr)
    finally:
        if out_path:
            fh.close()
        print(f"Bulk: wrote {written} lines to {out_path or 'stdout'}.", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Log Analytics — log generator")
    parser.add_argument("--rate", type=float, default=10.0, help="Lines per second (stream mode)")
    parser.add_argument("--out", type=str, default="", help="Output file path (default: stdout)")
    parser.add_argument("--duration", type=float, default=None, help="Stream duration in seconds")
    parser.add_argument("--spike-service", type=str, default=None, choices=SERVICES)
    parser.add_argument("--spike-at", type=float, default=None, help="Seconds after start to begin spike")
    parser.add_argument("--spike-duration", type=float, default=30.0, help="Spike duration in seconds")
    parser.add_argument("--bulk", type=int, default=0, help="Write N lines instantly (bulk mode)")
    args = parser.parse_args()

    if args.bulk > 0:
        run_bulk(args.bulk, args.out)
    else:
        run_stream(
            rate=args.rate,
            duration=args.duration,
            out_path=args.out,
            spike_service=args.spike_service,
            spike_at=args.spike_at,
            spike_duration=args.spike_duration,
        )


if __name__ == "__main__":
    main()
