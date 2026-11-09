"""Opt-in EnSmith-compatible local tracing for EnergyChain SDK.

Experimental producer adapter: metadata only, bounded and entirely local. It
neither uploads events nor requires EnSmith, EnergyChain Cloud or an LLM.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
import re
from threading import RLock
from uuid import uuid4

from .model_gateway import ModelTrace
from .observability import InMemoryTracer, TraceEvent


SPAN_SCHEMA_VERSION = "ensmith.span.v0"
_SAFE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]{0,127}\Z")


def _safe_name(value: object, fallback: str) -> str:
    """Reject arbitrary user content in fields intended to be identifiers."""
    return value if isinstance(value, str) and _SAFE_NAME.fullmatch(value) else fallback


def _safe_duration(value: object) -> float | None:
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        try:
            duration = float(value)
        except (OverflowError, ValueError):
            return None
        if isfinite(duration) and duration >= 0:
            return duration
    return None


def _safe_tokens(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= 2**63 - 1 else None


def _utc_timestamp(value: object) -> datetime:
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    # Invalid/unaware source timestamps are not silently assigned UTC meaning.
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class EnSmithSpan:
    """Local span envelope with no input/output, identity or free-form data fields."""

    trace_id: str
    span_id: str
    operation: str
    source: str
    outcome: str
    timestamp: datetime
    duration_ms: float | None = None
    parent_span_id: str | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def to_dict(self) -> dict[str, str | float | int | None]:
        """Return a JSON-serializable, versioned, metadata-only record."""
        return {
            "schema_version": SPAN_SCHEMA_VERSION,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation,
            "source": self.source,
            "outcome": self.outcome,
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat(),
            "duration_ms": self.duration_ms,
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


class EnSmithTracer(InMemoryTracer):
    """Capture SDK events as bounded, local, EnSmith-compatible spans.

    Pass this tracer to EnergyChain(tracer=...) to capture actual tool
    execution. record_model_trace is an optional ModelGateway callback.
    No network, credential loading, background thread, or SDK behavior change.
    """

    def __init__(self, max_events: int = 1000) -> None:
        super().__init__(max_events=max_events)
        self._span_lock = RLock()
        self._spans: list[EnSmithSpan] = []
        self._correlations: OrderedDict[str, str] = OrderedDict()

    def _trace_id(self, correlation_id: str | None = None) -> str:
        # Original correlation IDs are never included in exported telemetry.
        if not correlation_id or not isinstance(correlation_id, str) or len(correlation_id) > 128:
            return uuid4().hex
        if correlation_id in self._correlations:
            self._correlations.move_to_end(correlation_id)
            return self._correlations[correlation_id]
        trace_id = uuid4().hex
        self._correlations[correlation_id] = trace_id
        if len(self._correlations) > self.max_events:
            self._correlations.popitem(last=False)
        return trace_id

    def _append(self, span: EnSmithSpan) -> None:
        self._spans.append(span)
        if len(self._spans) > self.max_events:
            del self._spans[:-self.max_events]

    def record(self, event: TraceEvent) -> None:
        # Retain the original SDK event semantics and local event history.
        super().record(event)
        with self._span_lock:
            self._append(EnSmithSpan(
                trace_id=self._trace_id(event.correlation_id),
                span_id=uuid4().hex,
                operation=_safe_name(event.operation, "unknown_operation"),
                source="energychain.tool",
                outcome=(event.outcome if event.outcome in ("success", "denied_or_failed")
                         else "unknown"),
                timestamp=_utc_timestamp(event.timestamp),
                duration_ms=_safe_duration(event.duration_ms),
            ))

    def record_model_trace(self, event: ModelTrace, *,
                           correlation_id: str | None = None,
                           parent_span_id: str | None = None) -> None:
        """Accept explicit ModelGateway metadata; never store prompts or output."""
        with self._span_lock:
            self._append(EnSmithSpan(
                trace_id=self._trace_id(correlation_id),
                span_id=uuid4().hex,
                parent_span_id=(parent_span_id if isinstance(parent_span_id, str)
                                and re.fullmatch(r"[a-f0-9]{32}", parent_span_id)
                                else None),
                operation="model.generate",
                source="energychain.model_gateway",
                outcome="success" if event.success else "failed",
                timestamp=datetime.now(timezone.utc),
                duration_ms=_safe_duration(event.duration_ms),
                provider=_safe_name(event.provider, "unknown_provider"),
                model=_safe_name(event.model, "unknown_model"),
                input_tokens=_safe_tokens(event.usage.input_tokens),
                output_tokens=_safe_tokens(event.usage.output_tokens),
                total_tokens=_safe_tokens(event.usage.total_tokens),
            ))

    def spans(self) -> list[EnSmithSpan]:
        """Snapshot of local spans, oldest first; returns no mutable internals."""
        with self._span_lock:
            return list(self._spans)

    def span_dicts(self) -> list[dict[str, str | float | int | None]]:
        """Produce locally serializable envelopes for a future opt-in transport."""
        return [span.to_dict() for span in self.spans()]
