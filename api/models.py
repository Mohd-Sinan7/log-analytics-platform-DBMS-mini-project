"""
models.py — Pydantic response models for the Log Analytics API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    id: int
    doc_id: UUID
    ts: datetime
    severity: str
    service: str
    host: str
    trace_id: Optional[str] = None
    message: str


class LogsResponse(BaseModel):
    data: list[LogEntry]
    next_cursor: Optional[str] = Field(
        None,
        description="Opaque keyset cursor; pass as ?cursor= in the next request",
    )
    total_returned: int


class SearchHit(BaseModel):
    id: int
    doc_id: UUID
    ts: datetime
    severity: str
    service: str
    host: str
    trace_id: Optional[str] = None
    message: str
    score: Optional[float] = None


class SearchResponse(BaseModel):
    data: list[SearchHit]
    total_hits: int


class ErrorRateBucket(BaseModel):
    bucket: datetime
    service: str
    error_count: int
    total_count: int
    error_rate: float


class ErrorRateResponse(BaseModel):
    data: list[ErrorRateBucket]
    interval: str


class TopHost(BaseModel):
    host: str
    count: int


class TopHostsResponse(BaseModel):
    data: list[TopHost]
    severity: str


class AnomalyEntry(BaseModel):
    id: int
    detected_at: datetime
    bucket: datetime
    service: str
    metric: str
    value: float
    baseline_mean: float
    baseline_std: float
    zscore: float


class AnomaliesResponse(BaseModel):
    data: list[AnomalyEntry]


class HealthResponse(BaseModel):
    status: str
    postgres: str
    elasticsearch: str
