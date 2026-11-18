"""
config.py — Environment-driven configuration for the ingest agent.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    """All configuration sourced from environment variables."""

    # PostgreSQL
    postgres_host: str = field(default_factory=lambda: os.environ.get("POSTGRES_HOST", "localhost"))
    postgres_port: int = field(default_factory=lambda: int(os.environ.get("POSTGRES_PORT", "5432")))
    postgres_db: str   = field(default_factory=lambda: os.environ.get("POSTGRES_DB", "logs"))
    postgres_user: str = field(default_factory=lambda: os.environ.get("POSTGRES_USER", "logs"))
    postgres_password: str = field(default_factory=lambda: os.environ.get("POSTGRES_PASSWORD", "logspassword"))

    # Elasticsearch
    es_host: str = field(default_factory=lambda: os.environ.get("ES_HOST", "http://localhost:9200"))

    # Ingest tuning
    log_file: str     = field(default_factory=lambda: os.environ.get("LOG_FILE", "/var/log/app/app.log"))
    batch_size: int   = field(default_factory=lambda: int(os.environ.get("INGEST_BATCH_SIZE", "1000")))
    flush_interval: float = field(default_factory=lambda: float(os.environ.get("INGEST_FLUSH_INTERVAL", "1.0")))
    state_file: str   = field(default_factory=lambda: os.environ.get("INGEST_STATE_FILE", "/tmp/ingest_state.json"))

    @property
    def postgres_dsn(self) -> str:
        """asyncpg connection DSN."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def get_config() -> Config:
    """Return a Config instance populated from the environment."""
    return Config()
