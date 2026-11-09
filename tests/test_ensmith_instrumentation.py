"""INC-SMITH-001A / SMITH-F-001 / NFR-OBS-001 verification."""
import json
from datetime import datetime, timezone

import pytest

from energychain import EnergyChain, EnSmithTracer
from energychain.model_gateway import ModelTrace, TokenUsage
from energychain.observability import TraceEvent
from energychain.security import Principal
from energychain.exceptions import PermissionDenied
from energychain.connectors import HybridSiteSimulator


def build_chain(tracer):
    chain = EnergyChain(tracer=tracer)
    chain.add_connector("sim", HybridSiteSimulator())
    return chain


def test_real_tool_success_and_failure_are_traced():
    tracer = EnSmithTracer()
    chain = build_chain(tracer)
    authorized = chain.principal("dev", allowed_sites={"demo-site"})
    assert len(chain.tools.invoke("discover_assets", authorized, "demo-site")) == 4
    unauthorized = Principal("outsider", frozenset({"other-site"}))
    with pytest.raises(PermissionDenied):
        chain.tools.invoke("discover_assets", unauthorized, "demo-site")
    assert [span.outcome for span in tracer.spans()] == ["success", "denied_or_failed"]
    assert [e.outcome for e in tracer.events()] == ["success", "denied_or_failed"]
    assert all(s.source == "energychain.tool" for s in tracer.spans())


def test_default_span_dict_never_contains_sensitive_sdk_event_fields():
    secret = "super-secret-provider-token"
    tracer = EnSmithTracer()
    tracer.record(TraceEvent(
        operation="get_battery_state", principal_id="person-private", site_id="site-private",
        outcome="denied_or_failed", detail=secret,
    ))
    output = json.dumps(tracer.span_dicts())
    for sensitive in (secret, "person-private", "site-private", "detail", "principal_id", "site_id"):
        assert sensitive not in output
    assert '"schema_version": "ensmith.span.v0"' in output


def test_model_metadata_only_and_json_serializable():
    tracer = EnSmithTracer()
    event = ModelTrace("openai", "model-1", 13.0, TokenUsage(7, 3, 10), True)
    tracer.record_model_trace(event, correlation_id="workflow-private")
    payload = tracer.span_dicts()[0]
    assert payload["provider"] == "openai"
    assert payload["input_tokens"] == 7
    assert payload["total_tokens"] == 10
    assert payload["source"] == "energychain.model_gateway"
    assert "workflow-private" not in json.dumps(payload)
    assert "prompt" not in payload and "response" not in payload


def test_correlation_groups_span_ids_remain_distinct_and_buffer_bounded():
    tracer = EnSmithTracer(max_events=2)
    for op in ("first", "second"):
        tracer.record(TraceEvent(op, "x", "site", "success", correlation_id="shared-private-id"))
    one, two = tracer.spans()
    assert one.trace_id == two.trace_id and one.span_id != two.span_id
    tracer.record(TraceEvent("third", "x", "site", "success", correlation_id="other"))
    assert len(tracer.spans()) == 2
    assert len(tracer.events()) == 2
    assert "shared-private-id" not in json.dumps(tracer.span_dicts())


def test_invalid_names_timing_and_utc_timestamp_are_handled_safely():
    tracer = EnSmithTracer()
    tracer.record(TraceEvent(
        operation="secret=123\nunsafe", principal_id="secret", site_id="secret",
        outcome="unsupported-value", duration_ms=float("nan"),
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ))
    payload = tracer.span_dicts()[0]
    assert payload["operation"] == "unknown_operation"
    assert payload["outcome"] == "unknown"
    assert payload["duration_ms"] is None
    assert payload["timestamp"].startswith("2026-01-01")


def test_plain_sdk_tracer_unchanged_and_no_cloud_is_required():
    plain = build_chain(None)
    actor = plain.principal("local", allowed_sites={"demo-site"})
    assert len(plain.tools.invoke("discover_assets", actor, "demo-site")) == 4
    assert len(plain.tracer.events()) == 1
    assert not isinstance(plain.tracer, EnSmithTracer)


def test_correlation_and_parent_span_input_are_bounded():
    tracer = EnSmithTracer(max_events=1)
    tracer.record_model_trace(
        ModelTrace("openai", "model-1", 0.0, TokenUsage(1, 2, 3), True),
        correlation_id="sensitive-id" * 1000, parent_span_id="private-secret",
    )
    span = tracer.spans()[0]
    assert span.parent_span_id is None
    assert "sensitive-id" not in json.dumps(span.to_dict())
    tracer.record_model_trace(ModelTrace("openai", "model-1", 0.0, TokenUsage(), False))
    assert len(tracer.spans()) == 1
