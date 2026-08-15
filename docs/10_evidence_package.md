# Stage 9 — Evidence Package

The structured, cited, validated object the LLM consumes **instead of raw
retrieval output**. Built on V3; consumes the existing HybridRetriever — no
retrieval logic duplicated or changed.

## Architecture / flow

```
Question → Hybrid Retrieval (dense+BM25+RRF) → Evidence Package
         → LLM Context (grounded prompt) → Grounded Answer (with citations)
```

The generator (Stage 12) will only ever receive the **formatted Evidence
Package**, never a database row.

## Components
| Class | Role |
|---|---|
| `EvidenceItem` / `EvidencePackage` | typed model with every field the LLM needs (below) |
| `EvidenceBuilder` | RetrievalResults → items: resolves text, derives source type + typed citation, computes confidence, writes an explicit `retrieval_reason` |
| `EvidenceFormatter` | `to_context()` = the grounded prompt (numbered, cited blocks + cite-`[n]` instruction); `citation_index()` = typed nav data for the **Citation Explorer** |
| `EvidenceSerializer` | JSON to/from + save/load + `size_bytes` |
| `EvidenceValidator` | ordering, score/confidence ranges, citation↔source-type consistency, required fields, missing text |
| `EvidenceService` | wires retriever + text resolver + catalog into a ready builder (owns Qdrant + SQLite handles) |

### EvidenceItem fields
`rank, chunk_id, parent_chunk, text, retrieval_score, dense_score, bm25_score,
fused_score, semantic_similarity, confidence, retrieval_reason, source_type,
resource_id, document_title, heading, section_path, page, page_end, slide,
timestamp, language, citation, metadata`.

### Typed citations (Citation Explorer foundation)
`source_type` is derived from the anchors: **pdf** (`p.194`), **slide**
(`slide 7`), **video** (`12:34`), **web** (domain), notebook, document. The
`citation_index()` output carries page/slide/timestamp so the future Citation
Explorer can deep-link into the source.

### Confidence
`confidence = 0.5·semantic_similarity + 0.5·rank_factor` (rank_factor decays with
position), clamped [0,1]; `overall_confidence` = mean of the top-3 item
confidences. Reported as a calibrated grounding signal (used by Research Mode's
low-confidence trigger later).

## Configuration & CLI
```powershell
ala evidence "What is a foreign key and referential integrity?" --top-k 6
ala evidence "..." --filter course=dmv --json      # full package as JSON
ala evidence --benchmark                            # timing/size + figures
```

## Validation
`tests/test_evidence.py` (8 tests): field/source-type derivation, typed citations
(page/slide/timestamp), confidence range + ordering, formatter context + citation
index, serialization round-trip + size, validator passes well-formed, validator
catches bad citation / out-of-order / missing text.

## Benchmark (5 real queries, top-6)
All packages **valid, 0 errors**, overall confidence **0.84–0.87**, serialized
**~10–12 KB**. Steady-state build **~0.4–1.2 s** (dominated by e5 query encoding +
Qdrant search — the retrieval cost; evidence assembly itself is sub-millisecond).
The first query includes a one-time ~27 s e5 model load. Report + figures:
`reports/stage9_evidence/` (pipeline diagram, evidence breakdown, sample package).

## Live example
Query *"What is a foreign key and referential integrity?"* → 3–6 grounded items
from the DB reference book with citations `[db-reference-book, p.194]`, confidence
0.95 on the top item, and reasons like *"dense #1 (cos 0.902) + BM25 #1 (score
30.08) -> fused 0.0230"*.

## Honest limitations
- Confidence is a heuristic blend of semantic similarity + rank (calibrated, not
  a learned probability); good enough for the Research-Mode gate, refine later.
- `document_title` falls back to a slug-derived title when the catalog lacks one.
- No LLM yet — the package is validated structurally; answer faithfulness is
  measured in Stage 13.

## Extension points (per architecture)
- **Citation Explorer** consumes `EvidenceFormatter.citation_index()` (typed
  page/slide/timestamp records) — ready now.
- **GraphRAG** (Stage 12) will add `graph_evidence` alongside chunk evidence in
  the same package; `EvidenceItem.metadata`/reserved structure leaves room.
- **Web citations** already have a `source_type=web` path for Research Mode.
