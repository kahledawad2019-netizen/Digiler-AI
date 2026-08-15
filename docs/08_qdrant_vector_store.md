# Stage 5 — Qdrant Vector Store

The production vector database layer. Qdrant is the official store (not Chroma).
Built on V3; integrates with the Embedding stage; nothing earlier modified.

## Design (SOLID / DI)

Retrieval depends only on the `VectorStore` interface — the backend is swappable.

```
        ┌──────────────── VectorStore (Protocol) ────────────────┐
        │ ensure_collection · upsert · delete · delete_by_resource │
        │ search(filters) · count · health · stats · close         │
        └──────────────────────────────────────────────────────────┘
                                   ▲
                        QdrantVectorStore  (qdrant-client, local/`:memory:`)
                                   ▲
   get_vector_store(settings, dim) ── factory ── VectorStoreConfig
                                   ▲
   VectorIndexer: EmbeddingStore(vectors) + ChunkStore(metadata) → payload → upsert
   EmbeddingService(vector_store=…): embeds AND populates Qdrant in one pass
```

### Deployment: local mode, zero-infra
`QdrantVectorStore` uses qdrant-client **local mode** — `QdrantClient(path=…)` —
so there is **no server process** (consistent with the SQLite/ChromaDB rationale
in V3; Qdrant supersedes ChromaDB per the current directive). `:memory:` is used
by tests and the benchmark. The code is **server-ready**: point `location` at a
`http://…` URL and nothing else changes.

### Components / files
| File | Responsibility |
|---|---|
| `base.py` | `VectorStore` protocol, `VectorPoint`, `SearchHit` |
| `config.py` | `VectorStoreConfig` (provider/location/collection/distance/batch) |
| `payload.py` | payload schema (citation + filter fields) + deterministic `point_id` (UUID5 of chunk_id) |
| `qdrant_store.py` | `QdrantVectorStore` — collections, batched upsert + **vector validation**, id/resource delete, filtered search, count, health, stats |
| `factory.py` | `get_vector_store(settings, dim)` |
| `indexer.py` | `VectorIndexer` — stored embeddings → Qdrant; advances `vector_status` |
| `benchmark.py` | insert speed · search latency (mean/p95) · memory · storage · scalability |
| `report.py` | scalability benchmark on real corpus vectors + charts |

### Point IDs & payload
Chunk ids are strings; Qdrant needs UUID/int ids, so each chunk maps to a
deterministic `uuid5(chunk_id)` (idempotent upserts) with the real `chunk_id`
kept in the payload. Payload carries `resource_id`, `track/course/module`,
`chunk_type`, `page/page_end/slide/timestamp`, `section_path/heading`,
`topics/keywords`, `language`, `embedding_model/version` — the fields retrieval
filtering and the Evidence Package (Stage 9) need.

## CLI
```powershell
ala index --all                          # index every embedded resource into Qdrant
ala index --resource <id>                # index one
ala index --search "foreign keys" --top-k 5 --filter course=dmv
ala index --stats        # collection stats
ala index --health       # health check
ala index --benchmark --model hashing    # scalability benchmark + charts
```

## Capabilities (Stage-5 checklist)
Collection manager ✓ · payload schema ✓ · incremental/idempotent indexing ✓ ·
update (re-upsert) ✓ · delete (by id & by resource) ✓ · batch insert ✓ ·
metadata filtering (value + any-of) ✓ · versioning (embedding_version in payload,
`recreate`) ✓ · health check ✓ · vector validation (dim + finite) ✓ ·
EmbeddingService directly populates Qdrant ✓.

## Validation
Unit + integration tests in `tests/test_vectorstore.py` (upsert/search/count,
value + any-of filtering, delete by id & resource, idempotency, vector
validation, health/stats, payload+point_id, and the EmbeddingService→Qdrant
integration). Benchmark + charts: `reports/stage5_qdrant/` (`ala index --benchmark`).

## Honest notes
- Local mode is **brute-force** (exact search) and persists to disk on upsert, so
  **bulk indexing of the full 21.8 k-vector corpus is slow** (minutes). This is a
  local-mode property, not a code issue; a Qdrant **server** (HNSW, batched gRPC)
  is the production path for large corpora — the interface and code already
  support it via `location=<url>`.
- The benchmark runs in `:memory:` up to a few thousand real vectors to measure
  insert throughput and search latency without touching the persistent index.
