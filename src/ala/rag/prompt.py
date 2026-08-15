"""GraphPromptBuilder — render the ReasoningContext into a grounded prompt.

The prompt is graph-aware: it presents the concept scaffold (concepts,
relations, prerequisites) *and* the cited source evidence, then instructs the
model to answer **only** from the numbered evidence and cite every claim. This
string is the sole thing handed to the LLM — raw retrieval output never is.
"""

from __future__ import annotations

from ala.rag.models import ReasoningContext

_SYSTEM = (
    "You are Digiler AI, a study assistant for Digilians course materials. "
    "Answer the question using ONLY the numbered evidence below. "
    "Cite every claim with its tag, e.g. [C1] for a source passage or [K1] for a "
    "concept. Do NOT use any outside knowledge. If the evidence is insufficient, "
    "say exactly what is missing. Be concise and accurate."
)


class GraphPromptBuilder:
    def build(self, ctx: ReasoningContext) -> str:
        return "\n".join(self._sections(ctx))

    def _sections(self, ctx: ReasoningContext) -> list[str]:
        out = [_SYSTEM, ""]

        if ctx.concepts:
            out.append("# CONCEPTS (knowledge graph)")
            for c in ctx.concepts:
                tag = "seed" if c.hop == 0 else f"{c.hop}-hop via {c.relationship}"
                out.append(f"[{c.cid}] {c.concept} ({tag}, conf {c.confidence:.2f})")
            out.append("")

        if ctx.relations:
            out.append("# RELATIONS")
            for r in ctx.relations:
                out.append(f"- {r.source} --{r.relationship}--> {r.target}")
            out.append("")

        if ctx.prerequisites:
            out.append("# PREREQUISITES: " + ", ".join(ctx.prerequisites))
            out.append("")

        out.append("# EVIDENCE (sources)")
        for c in ctx.chunks:
            out.append(f"[{c.cid}] {c.citation}")
            out.append(c.text)
            out.append("")

        out.append("# QUESTION")
        out.append(ctx.question)
        out.append("")
        out.append("# ANSWER (grounded, cite every claim):")
        return out
