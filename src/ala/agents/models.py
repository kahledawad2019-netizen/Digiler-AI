"""Agent value types + the Tool abstraction (shared with Function Calling, Stage 23)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ala.core.enums import _StrEnum


class AgentRole(_StrEnum):
    TUTOR = "tutor"
    QUIZ = "quiz"
    EVALUATOR = "evaluator"
    PLANNER = "planner"
    RESEARCH = "research"
    WEB_RESEARCH = "web_research"
    CURATOR = "knowledge_curator"
    COORDINATOR = "coordinator"


@dataclass
class AgentRequest:
    text: str = ""
    student_id: str = "default"
    concept: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    agent: str
    role: str
    output: str
    data: dict = field(default_factory=dict)
    citations: list[dict] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"agent": self.agent, "role": self.role, "output": self.output,
                "data": self.data, "citations": self.citations, "tools_used": self.tools_used}


@dataclass
class Tool:
    """A named capability an agent (or the function-calling layer) can invoke.

    Every tool wraps an *existing* service method — the single source of truth for
    that capability — so there is exactly one retrieval path, one ingestion path, etc.
    """
    name: str
    description: str
    func: Callable[..., dict]
    schema: dict = field(default_factory=dict)      # arg name → type hint (for Stage 23)

    def run(self, **kwargs) -> dict:
        return self.func(**kwargs)
