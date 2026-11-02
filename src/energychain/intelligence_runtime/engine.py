"""Evidence-backed, bounded energy workflow execution for SDK consumers.

The model can propose plans and interpret data but never invokes tools itself.
No unbounded loops, arbitrary code execution or equipment-control tools.
"""
from __future__ import annotations
import dataclasses
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import re
from time import perf_counter
from typing import Any, Mapping
from uuid import uuid4

from energychain.security import Permission
from energychain.intelligence_runtime.contracts import (
    EvidenceError, EvidenceRecord, InputRef, IntelligencePlan,
    IntelligenceResult, OutputRef, PlanRejected, SourceEvidence, StepRecord,
    ToolStep, VerifiedFinding,
)

_ID = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,63}$")
_FORBIDDEN_KEYS = ("api_key", "token", "secret", "password", "authorization", "credential", "private_key")
_MAX_BYTES = 512_000
_OPERATORS = {"lt":lambda a,b:a<b,"le":lambda a,b:a<=b,"gt":lambda a,b:a>b,
              "ge":lambda a,b:a>=b,"eq":lambda a,b:a==b,"ne":lambda a,b:a!=b}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(name: str) -> bool:
    lower = name.lower()
    return any(marker in lower for marker in _FORBIDDEN_KEYS)


def _clean(data: Any, *, depth: int = 0, serialize: bool = True) -> Any:
    """Redact and bound data; preserve typed leaves for tool invocation when requested."""
    if depth > 20:
        raise EvidenceError("output nesting exceeds evidence limit")
    if dataclasses.is_dataclass(data) and not isinstance(data, type):
        return _clean({f.name:getattr(data, f.name) for f in dataclasses.fields(data)},
                      depth=depth+1, serialize=serialize)
    if isinstance(data, datetime):
        return data.isoformat() if serialize else data
    if isinstance(data, Enum):
        return _clean(data.value, depth=depth+1) if serialize else data
    if isinstance(data, Mapping):
        if len(data)>2000:
            raise EvidenceError("output mapping too large")
        return {str(k):"[REDACTED]" if _redact(str(k)) else
                _clean(v,depth=depth+1,serialize=serialize)
                for k,v in data.items()}
    if isinstance(data,(tuple,list,set,frozenset)):
        if len(data)>4000:
            raise EvidenceError("output collection too large")
        return [_clean(x,depth=depth+1,serialize=serialize) for x in
                (sorted(data,key=str) if isinstance(data,(set,frozenset)) else data)]
    if isinstance(data,float) and not math.isfinite(data):
        raise EvidenceError("nonfinite output rejected")
    if data is None or isinstance(data,(str,int,float,bool)):
        if isinstance(data,str) and len(data)>100_000:
            raise EvidenceError("output string too large")
        return data
    raise EvidenceError("tool returned unsupported value type: "+type(data).__name__)


def _value_types(data: Any) -> Any:
    """Distinguish typed references/datetimes from lookalike serialized literals."""
    if dataclasses.is_dataclass(data) and not isinstance(data, type):
        return {"dataclass": type(data).__module__ + "." + type(data).__qualname__,
                "fields": _value_types({f.name: getattr(data, f.name)
                                        for f in dataclasses.fields(data)})}
    if isinstance(data, Mapping):
        return {"mapping": {str(k): "[REDACTED]" if _redact(str(k)) else _value_types(v)
                            for k, v in data.items()}}
    if isinstance(data, (tuple, list, set, frozenset)):
        sequence = sorted(data, key=str) if isinstance(data, (set, frozenset)) else data
        return {"sequence": [_value_types(v) for v in sequence]}
    return type(data).__module__ + "." + type(data).__qualname__


def _blob(value: Any) -> bytes:
    b=json.dumps(_clean(value),sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",", ":")).encode()
    if len(b)>_MAX_BYTES:
        raise EvidenceError("serialized evidence exceeds size cap")
    return b


def _hash(value: Any) -> str:
    return hashlib.sha256(_blob(value)).hexdigest()


def _reading_sources(value: Any) -> tuple[SourceEvidence,...]:
    out=[]
    def walk(node, depth=0):
        if depth>16 or len(out)>200:
            return
        if isinstance(node, Mapping):
            # Cleaned EnergyReading, or direct SDK reading dictionary.
            if {"asset_id","metric","value","timestamp","source","quality"}.issubset(node):
                metric=node["metric"]
                units={"power_w":"W","energy_wh":"Wh","state_of_charge_pct":"%",
                       "capacity_wh":"Wh","voltage_v":"V","current_a":"A",
                       "frequency_hz":"Hz","temperature_c":"°C"}
                out.append(SourceEvidence(str(node["asset_id"]),str(metric),node["value"],
                        units.get(str(metric),""),str(node["source"]),str(node["quality"]),str(node["timestamp"])))
            for val in node.values():
                walk(val,depth+1)
        elif isinstance(node,list):
            for val in node:
                walk(val,depth+1)
    walk(value)
    return tuple(out[:200])


def _lookup(data: Any, path: tuple[str | int,...]) -> Any:
    cur=data
    for part in path:
        if isinstance(cur,Mapping) and isinstance(part,str) and part in cur:
            cur=cur[part]
        elif isinstance(cur,(tuple,list)) and isinstance(part,int) and 0<=part<len(cur):
            cur=cur[part]
        else:
            raise PlanRejected("output reference does not exist")
    return cur


def _resolve(value: Any,inputs:Mapping[str,Any],outputs:Mapping[str,Any], *, depth=0):
    if depth>16:
        raise PlanRejected("input depth exceeded")
    if isinstance(value,InputRef):
        if value.name not in inputs:
            raise PlanRejected("missing declared task input: "+value.name)
        return inputs[value.name]
    if isinstance(value,OutputRef):
        if value.step_id not in outputs:
            raise PlanRejected("output reference is unavailable: "+value.step_id)
        return _lookup(outputs[value.step_id],value.path)
    if isinstance(value,Mapping):
        return {str(k):_resolve(v,inputs,outputs,depth=depth+1) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [_resolve(v,inputs,outputs,depth=depth+1) for v in value]
    return value


def _references(value:Any):
    if isinstance(value,OutputRef):
        yield value.step_id
    elif isinstance(value,Mapping):
        for v in value.values():
            yield from _references(v)
    elif isinstance(value,(tuple,list)):
        for v in value:
            yield from _references(v)


def _parse_plan(raw:Any)->IntelligencePlan:
    """Strict model plan: JSON literals and references, never Python expressions."""
    if isinstance(raw,IntelligencePlan):
        return raw
    if not isinstance(raw,Mapping) or set(raw)!={"id","version","steps"}:
        raise PlanRejected("plan must contain id, version and steps")
    def transform(v):
        if isinstance(v,Mapping):
            if set(v)=={"$input"} and isinstance(v["$input"],str):
                return InputRef(v["$input"])
            if set(v)=={"$output","path"} and isinstance(v["$output"],str) and isinstance(v["path"],list):
                if not all(isinstance(x,(str,int)) and not isinstance(x,bool) for x in v["path"]):
                    raise PlanRejected("invalid output path")
                return OutputRef(v["$output"],tuple(v["path"]))
            return {k:transform(x) for k,x in v.items()}
        if isinstance(v,list):
            return [transform(x) for x in v]
        return v
    steps=raw["steps"]
    if not isinstance(steps,list):
        raise PlanRejected("steps must be an array")
    out=[]
    for x in steps:
        if not isinstance(x,Mapping) or not {"id","tool","arguments"}.issubset(x) or set(x)-{"id","tool","arguments","depends_on"} or not isinstance(x["arguments"],Mapping):
            raise PlanRejected("invalid model-supplied step")
        out.append(ToolStep(x["id"], x["tool"], transform(x["arguments"]),
                            tuple(x.get("depends_on", ()))))
    return IntelligencePlan(raw["id"],raw["version"],tuple(out))


def _plan_validation(plan:IntelligencePlan, permitted:set[str], max_steps:int):
    if not isinstance(plan.id,str) or not _ID.fullmatch(plan.id) or not isinstance(plan.version,int) or isinstance(plan.version,bool) or plan.version<1:
        raise PlanRejected("invalid plan identifier or version")
    if not 1<=len(plan.steps)<=max_steps:
        raise PlanRejected("workflow step limit exceeded")
    seen=set()
    for s in plan.steps:
        if not isinstance(s.id,str) or not _ID.fullmatch(s.id) or s.id in seen:
            raise PlanRejected("duplicate/invalid step id")
        if s.tool not in permitted or s.tool=="energy_intelligence":
            raise PlanRejected("workflow tool is not permitted: "+str(s.tool))
        if not isinstance(s.arguments,Mapping) or len(s.arguments)>64 or any(_redact(str(k)) for k in s.arguments):
            raise PlanRejected("invalid or secret-bearing step arguments")
        if "site_id" in s.arguments or "principal" in s.arguments:
            raise PlanRejected("step arguments cannot override the trusted scope")
        if any(ref not in seen for ref in (*_references(s.arguments), *s.depends_on)):
            raise PlanRejected("a step may only depend on earlier successful steps")
        seen.add(s.id)
    for rule in plan.rules:
        if not isinstance(rule.id,str) or not _ID.fullmatch(rule.id) or not isinstance(rule.value,OutputRef) or rule.value.step_id not in seen or rule.op not in _OPERATORS:
            raise PlanRejected("invalid evidence rule")
        if not isinstance(rule.threshold,(int,float)) or isinstance(rule.threshold,bool) or not math.isfinite(rule.threshold):
            raise PlanRejected("evidence rule threshold must be finite")


class EnergyIntelligence:
    """Read/analysis workflow engine. Authentication is supplied by the host application.

    No action control, external scheduling, implicit elevated permissions, or hosted service.
    """
    def __init__(self,sdk,*,model=None,store=None,max_steps:int=8,max_input_age_seconds:float|None=None):
        if not 1<=max_steps<=12:
            raise ValueError("max_steps must be 1..12")
        self.sdk,self.model,self.store,self.max_steps=sdk,model,store,max_steps
        self.max_input_age_seconds=max_input_age_seconds

    def _permitted(self,allowed_tools):
        choices={x["name"] for x in self.sdk.tools.describe()
                 if x["permission"] in (Permission.READ.value,Permission.ANALYZE.value)
                 and x["name"]!="energy_intelligence"}
        if allowed_tools is not None:
            choices.intersection_update(set(allowed_tools))
        return choices

    def _authorize_replay(self, result, permitted, principal, site_id):
        # Stored step records preserve every selected tool, including blocked steps.
        # Replaying a result must not outlive current tool, site or action permissions.
        if not 1 <= len(result.steps) <= self.max_steps:
            raise PlanRejected("stored workflow exceeds the current step limit")
        specs = {spec["name"]: spec for spec in self.sdk.tools.describe()}
        for step in result.steps:
            if step.tool not in permitted:
                raise PlanRejected("stored workflow tool is not permitted: " + step.tool)
            self.sdk.tools.policy.authorize(
                principal, site_id, Permission(specs[step.tool]["permission"]),
                action=step.tool, parameters=step.arguments)
        return result

    def _propose(self,task, inputs, permitted):
        if self.model is None:
            raise PlanRejected("AI planning requires an injected TextModel")
        if not permitted:
            raise PlanRejected("AI planning requires an explicit nonempty allowlist")
        desc=[s for s in self.sdk.tools.describe() if s["name"] in permitted]
        guide=("You plan READ/ANALYZE EnergyChain tools only. Respond with a single JSON object "
               "with EXACTLY id, version, steps. id='ai-task', version=1. steps is a list of "
               "{id,tool,arguments}, max "+str(self.max_steps)+". "
               "Use {'$input':'name'} for provided inputs; use {'$output':'step_id','path':['value']} "
               "for an earlier step result. Never invent readings or choose physical actions. "
               "Allowed tools: "+json.dumps(desc,sort_keys=True))
        answer=self.model.generate(guide,task,"Available input field names and values: "+json.dumps(_clean(inputs)))
        if not isinstance(answer,str) or len(answer)>16_384:
            raise PlanRejected("model plan too large")
        try:
            obj=json.loads(answer)
        except (ValueError,TypeError) as exc:
            raise PlanRejected("model returned invalid plan JSON") from exc
        return _parse_plan(obj)

    def run(self,*,task:str,principal,site_id:str,inputs:Mapping[str,Any]|None=None,
            plan:IntelligencePlan|Mapping[str,Any]|None=None,
            allowed_tools:set[str]|frozenset[str]|None=None,run_id:str|None=None,
            synthesize:bool=False)->IntelligenceResult:
        if not isinstance(task,str) or not 1<=len(task.strip())<=4096:
            raise PlanRejected("task must have 1..4096 characters")
        if not isinstance(site_id,str) or not site_id or len(site_id)>128:
            raise PlanRejected("invalid site id")
        if inputs is not None and not isinstance(inputs, Mapping):
            raise PlanRejected("task inputs must be a mapping")
        task_inputs=_clean(inputs if inputs is not None else {}, serialize=False)
        clean_inputs=_clean(task_inputs)
        _blob(clean_inputs)
        permitted=self._permitted(allowed_tools)
        # Auth check happens before LLM planning and prevents cross-site input exposure.
        self.sdk.tools.policy.authorize(principal,site_id,Permission.READ)
        if plan is None and allowed_tools is None:
            raise PlanRejected("AI-planned tasks require explicit allowed_tools")
        selected=_parse_plan(plan) if plan is not None else None
        if selected is not None:
            _plan_validation(selected,permitted,self.max_steps)
        rid=uuid4().hex if run_id is None else run_id
        if not isinstance(rid,str) or not 1<=len(rid)<=128 or any(ord(c)<32 for c in rid):
            raise PlanRejected("invalid run id")
        # The original request, rather than a nondeterministic model proposal, owns
        # the run id. A completed run can therefore replay while a provider is down.
        request_fingerprint=_hash({"task":task,"site":site_id,"principal":principal.id,
                                  "principal_sites":sorted(principal.allowed_sites),
                                  "plan":_clean(selected),"plan_types":_value_types(selected),
                                  "inputs":clean_inputs,"input_types":_value_types(task_inputs),
                                  "allowed_tools":sorted(permitted),"synthesize":synthesize,
                                  "max_steps":self.max_steps,
                                  "max_input_age_seconds":self.max_input_age_seconds})
        if self.store is not None:
            existing=self.store.replay(rid,principal.id,site_id,request_fingerprint)
            if existing is not None:
                return self._authorize_replay(existing,permitted,principal,site_id)
        if selected is None:
            selected=self._propose(task,clean_inputs,permitted)
            _plan_validation(selected,permitted,self.max_steps)
        if self.store is not None:
            existing=self.store.reserve(rid,principal.id,site_id,request_fingerprint)
            if existing is not None:
                return self._authorize_replay(existing,permitted,principal,site_id)
        values={}
        typed_values={}
        steps=[]
        evidence=[]
        findings=[]
        error=None
        for s in selected.steps:
            start=perf_counter()
            try:
                arguments=_resolve(s.arguments,task_inputs,typed_values)
                safe_arguments=_clean(arguments)
                _blob(safe_arguments)
                result=self.sdk.tools.invoke(s.tool,principal,site_id,arguments=arguments)
                cleaned=_clean(result)
                _blob(cleaned)
                sources=_reading_sources(cleaned)
                if self.max_input_age_seconds is not None:
                    now=datetime.now(timezone.utc)
                    for src in sources:
                        ts=datetime.fromisoformat(src.observed_at.replace("Z","+00:00"))
                        age_seconds = (now - ts).total_seconds() if ts.tzinfo else float("inf")
                        if age_seconds < -30 or age_seconds > self.max_input_age_seconds:
                            raise EvidenceError("stale or future energy reading")
                evidence_id=f"{rid}:{s.id}"
                parents=tuple(dict.fromkeys(f"{rid}:{dep}" for dep in
                     (*_references(s.arguments), *s.depends_on)))
                record=EvidenceRecord(evidence_id,s.id,s.tool,_hash(safe_arguments),
                                      _hash(cleaned),sources,cleaned,_now(),parents)
                values[s.id]=cleaned
                typed_values[s.id]=_clean(result,serialize=False)
                evidence.append(record)
                steps.append(StepRecord(s.id,s.tool,"succeeded",evidence_id,
                                        round((perf_counter()-start)*1000,3),safe_arguments))
            except Exception as exc:
                error=type(exc).__name__
                steps.append(StepRecord(s.id,s.tool,"failed",None,
                                        round((perf_counter()-start)*1000,3),{},error))
                break
        if error and len(steps)<len(selected.steps):
            for remaining in selected.steps[len(steps):
                ]:
                steps.append(StepRecord(remaining.id,remaining.tool,"blocked",None,0.0,{},
                                        "UpstreamStepFailed"))
        for rule in selected.rules if error is None else ():
            try:
                val=_lookup(values[rule.value.step_id],rule.value.path)
                if not isinstance(val,(int,float)) or isinstance(val,bool) or not math.isfinite(val):
                    raise EvidenceError("rule operand is not a finite number")
                ev_id=f"{rid}:{rule.value.step_id}"
                findings.append(VerifiedFinding(rule.id,rule.label,rule.severity,
                    _OPERATORS[rule.op](val,rule.threshold),float(val),rule.op,
                    float(rule.threshold),ev_id))
            except Exception as exc:
                error=type(exc).__name__
                break
        interpretation=None
        interp_status="not_requested"
        if synthesize and error is None:
            if self.model is None:
                interp_status="unavailable"
            else:
                try:
                    payload={"task":task,"outputs":values,
                             "evidence_ids":[x.id for x in evidence],
                             "verified_rule_evaluations":_clean(findings)}
                    interpretation=self.model.generate(
                        "Explain tool outputs only. Do not claim live devices, verified root causes or "
                        "equipment control. This is advisory, unverified LLM interpretation. "
                        "Do not claim facts beyond the provided evidence.",
                        task,json.dumps(payload,ensure_ascii=False,default=str))
                    if not isinstance(interpretation,str) or len(interpretation)>16_384:
                        raise EvidenceError("invalid model interpretation")
                    interp_status="generated_unverified"
                except Exception:
                    interpretation=None
                    interp_status="generation_failed"
        result=IntelligenceResult(rid,task,"failed" if error and not values else
            "partial" if error else "completed",selected.id,selected.version,site_id,
            values,tuple(steps),tuple(evidence),tuple(findings),interpretation,
            interp_status,error,_now(),_hash(selected),_hash(clean_inputs))
        if self.store is not None:
            self.store.finish(result)
        return result

    def register_tool(self,name:str="energy_intelligence"):
        """Allow invoking this engine as a step in existing EnergyWorkflow/ToolRegistry.

        Explicit plan only: do not expose model-powered planning as a nested tool.
        """
        from energychain.tools import ToolSpec
        if name!="energy_intelligence":
            raise ValueError("reserved tool name only")
        def handler(*,site_id,principal,task,plan,inputs=None):
            return self.run(task=task,site_id=site_id,principal=principal,
                            plan=plan,inputs=inputs,allowed_tools=self._permitted(None),synthesize=False)
        self.sdk.tools.register(ToolSpec(name,"Execute a bounded, evidence-backed read/analysis intelligence workflow",
                                         Permission.ANALYZE,handler,needs_principal=True))
        return self
