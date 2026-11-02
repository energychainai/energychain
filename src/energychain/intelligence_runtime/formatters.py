"""Presentation adapters. SDK returns data; host chooses the UI.

Do not use these as an authorization or data-validation boundary.
"""
from __future__ import annotations
import json
from energychain.intelligence_runtime.engine import _clean


def as_dict(result) -> dict:
    return _clean(result)


def to_json(result, *, indent=2) -> str:
    return json.dumps(as_dict(result), indent=indent, ensure_ascii=False, allow_nan=False)


def format_console(result) -> str:
    lines = [f"EnergyIntelligence · {result.status.upper()}",
             f"Run: {result.run_id}  Site: {result.site_id}",
             f"Plan: {result.plan_id}@{result.plan_version}",
             f"Task: {result.task}", "Steps:"]
    for step in result.steps:
        lines.append(f"  {step.id:<16} {step.status:<10} {step.tool}"
                     + (f"  [{step.error_code}]" if step.error_code else ""))
    if result.findings:
        lines.append("Deterministic checks:")
        for f in result.findings:
            lines.append(f"  {f.label}: {f.actual:g} {f.operator} {f.threshold:g} "
                         f"=> {'TRUE' if f.satisfied else 'FALSE'} [{f.evidence_id}]")
    lines.append(f"Evidence records: {len(result.evidence)}")
    if result.interpretation:
        lines.append("LLM interpretation [UNVERIFIED]: "+result.interpretation)
    if result.error_code:
        lines.append(f"Error type: {result.error_code}")
    return "\n".join(lines)
