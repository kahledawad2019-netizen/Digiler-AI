"""Project Context — the platform's machine-readable self-description (Task 5)."""

from ala.context.models import (
    ComponentInfo,
    ComponentStatus,
    ConfigurationInfo,
    CourseInfo,
    KnowledgeBaseStatus,
    ProjectContext,
)
from ala.context.service import ProjectContextService

__all__ = [
    "ProjectContext",
    "ProjectContextService",
    "ComponentInfo",
    "ComponentStatus",
    "ConfigurationInfo",
    "CourseInfo",
    "KnowledgeBaseStatus",
]
