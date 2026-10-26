"""Plug-in model interface; no vendor SDK dependency in framework core."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


class TextModel(ABC):
    @abstractmethod
    def generate(self, system: str, user: str, context: str) -> str: ...


@dataclass
class CallableTextModel(TextModel):
    """Bring your own LLM by passing any compatible Python callable.

    E.g. function(system: str, user: str, context: str) -> str.
    """
    fn: Callable[[str, str, str], str]

    def generate(self, system: str, user: str, context: str) -> str:
        return self.fn(system, user, context)
