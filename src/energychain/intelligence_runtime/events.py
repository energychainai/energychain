"""Optional event adapter for trusted in-process EnergyEventBus.

Delivery is best-effort and synchronous; use a durable external queue in production.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from energychain.intelligence_runtime.contracts import IntelligencePlan, IntelligenceResult


@dataclass(frozen=True)
class IntelligenceEventRule:
    category: str
    task: str
    plan: IntelligencePlan
    input_factory: Callable[[Any],dict[str,Any]]


class IntelligenceEventSubscription:
    """Host-owned service principal; event metadata never confers authorization."""
    def __init__(self,*,bus,engine,rule:IntelligenceEventRule,principal,
                 on_result:Callable[[IntelligenceResult],None]|None=None,
                 on_error:Callable[[Exception],None]|None=None):
        if on_error is None:
            raise ValueError("on_error callback required: EventBus suppresses listener exceptions")
        if engine.store is None:
            raise ValueError("event-triggered tasks require a durable run store for idempotency")
        if not rule.category or not callable(rule.input_factory):
            raise ValueError("invalid event rule")
        self.bus,self.engine,self.rule,self.principal=bus,engine,rule,principal
        self.on_result,self.on_error=on_result,on_error
        self._handle_id=bus.subscribe(self._received)

    def _received(self,event):
        if event.category!=self.rule.category:
            return
        try:
            # Only already-authorized service identity is used; no model-authored identity.
            result=self.engine.run(task=self.rule.task,principal=self.principal,
                                   site_id=event.site_id,inputs=self.rule.input_factory(event),
                                   plan=self.rule.plan,run_id="event:"+str(event.id))
            if self.on_result:
                self.on_result(result)
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            # EventBus currently swallows listener errors: observable error callback is required
            # for production integrations; no implicit retry is performed.

    def close(self):
        self.bus.unsubscribe(self._handle_id)
