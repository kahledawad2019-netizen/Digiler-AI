"""Stage 22 — AI Agents.

A multi-agent layer where each agent is a **role over the existing services** —
Tutor / Quiz / Evaluator / Planner / Research / Web-Research / Knowledge-Curator,
coordinated by a Coordinator. Every agent that retrieves does so through the
**existing GraphRAG / Research** stack — retrieval is never duplicated. The
framework is dependency-free by default (CrewAI is an optional seam). Fully
additive: agents compose existing capabilities as tools.
"""

from ala.agents.coordinator import Coordinator, Crew
from ala.agents.models import AgentRequest, AgentResult, AgentRole, Tool
from ala.agents.service import AgentService

__all__ = ["AgentService", "Coordinator", "Crew", "AgentRequest", "AgentResult",
           "AgentRole", "Tool"]
