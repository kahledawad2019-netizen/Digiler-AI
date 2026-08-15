"""Data model for the Project Context.

The ProjectContext is the platform's self-description: partly *declared*
(components, model choices — from context.declared.yaml) and partly *live*
(knowledge-base status, courses — read from the catalog and taxonomy). Future
agents read this object before acting, so it is deliberately plain and
machine-readable.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ala.core.clock import utcnow_iso
from ala.core.enums import _StrEnum

_Model = ConfigDict(extra="forbid", use_enum_values=True)


class ComponentStatus(_StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    DEFERRED = "deferred"


class ComponentInfo(BaseModel):
    model_config = _Model
    name: str
    kind: str                      # module|agent|tool|stage|policy|subsystem
    status: ComponentStatus = ComponentStatus.PLANNED
    phase: str | None = None
    notes: str | None = None


class ConfigurationInfo(BaseModel):
    model_config = _Model
    vector_store: str | None = None
    vector_store_status: ComponentStatus = ComponentStatus.PLANNED
    embedding_model: str | None = None
    embedding_status: ComponentStatus = ComponentStatus.PLANNED
    llm: str | None = None
    llm_status: ComponentStatus = ComponentStatus.PLANNED
    retrieval_strategy: str = "unset"
    graph_status: ComponentStatus = ComponentStatus.PLANNED
    student_model_status: ComponentStatus = ComponentStatus.PLANNED
    reinforcement_learning_status: ComponentStatus = ComponentStatus.PLANNED
    evaluation_status: ComponentStatus = ComponentStatus.PLANNED


class CourseInfo(BaseModel):
    model_config = _Model
    track: str
    course: str
    title: str
    modules: int = 0


class KnowledgeBaseStatus(BaseModel):
    model_config = _Model
    total_resources: int = 0
    total_bytes: int = 0
    indexed: int = 0
    pending: int = 0
    by_course: dict[str, int] = Field(default_factory=dict)
    by_language: dict[str, int] = Field(default_factory=dict)
    by_processing_status: dict[str, int] = Field(default_factory=dict)
    by_doc_type: dict[str, int] = Field(default_factory=dict)
    last_updated: str | None = None


class ProjectContext(BaseModel):
    """The whole self-description, ready to serialise to YAML/JSON."""

    model_config = _Model

    build_version: str
    architecture_baseline: str
    schema_version: str
    generated_at: str = Field(default_factory=utcnow_iso)

    configuration: ConfigurationInfo
    components: list[ComponentInfo] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)       # convenience projections
    tools: list[str] = Field(default_factory=list)
    courses: list[CourseInfo] = Field(default_factory=list)
    knowledge_base: KnowledgeBaseStatus = Field(default_factory=KnowledgeBaseStatus)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")

    def implemented(self) -> list[str]:
        return [c.name for c in self.components if c.status == ComponentStatus.IMPLEMENTED.value]

    def summary_line(self) -> str:
        done = len(self.implemented())
        return (
            f"ALA v{self.build_version} ({self.architecture_baseline}) | "
            f"{done}/{len(self.components)} components implemented | "
            f"{self.knowledge_base.total_resources} resources"
        )
