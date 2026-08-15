# Stage 4 — Embedding Pipeline

Model-agnostic embedding layer feeding the vector store (Stage 5) and retrieval
(Stage 6+). Built on Architecture V3; nothing earlier was modified.

## Design (SOLID / Dependency Inversion)

Retrieval never depends on a concrete model — only on the `Embedder` interface
and the `EmbeddingStore`. Switching models is a config change.

```
              ┌───────────── Embedder (Protocol) ─────────────┐
              │ embed_documents() · embed_query() · dim · version │
              └───────────────────────────────────────────────┘
                     ▲                         ▲
        HashingEmbedder                 SentenceTransformerEmbedder
   (dependency-free, always            (e5-small · bge-m3 · MiniLM;
    available; feature hashing)         lazy torch import; HF weights)
                     │                         │
   get_embedder(key) ◀── factory ── MODEL_SPECS (registry: HF name, dim, prefixes)
                     │
   EmbeddingService: ChunkStore → cache → batch embed → EmbeddingStore
                     │                        + stamp chunk metadata + status→embedded
```

### Components
| Module | Responsibility |
|---|---|
| `base.py` | `Embedder` protocol + `EmbeddingResult` |
| `config.py` | `EmbeddingConfig` + `MODEL_SPECS` registry (e5/bge-m3/MiniLM specs & prefixes) |
| `hashing.py` | `HashingEmbedder` — real char-ngram feature hashing (BLAKE2b, deterministic, L2-normalized). **Not a mock** — a genuine, lower-quality embedding that runs offline/CI. |
| `sentence_transformer.py` | `SentenceTransformerEmbedder` — lazy sentence-transformers; applies e5 `query:`/`passage:` prefixes automatically |
| `factory.py` | `get_embedder(key)` / `available_models()` / `transformer_available()` |
| `cache.py` | `EmbeddingCache` — content-hash keyed, per-version JSONL (skips re-embedding identical text) |
| `store.py` | `EmbeddingStore` — versioned vectors (`<model>.jsonl`) + manifest (model/version/dim/count/timestamps); numpy matrix on demand |
| `pipeline.py` | `EmbeddingService` — incremental batch embedding; stamps chunk metadata `embedding_model/version/dim`; advances resource status → `embedded` via the Registry |
| `benchmark.py` | time · throughput · compute memory · dim · storage · query latency · **coherence** (intra- vs inter-resource cosine gap) |
| `viz.py` | PCA · t-SNE · UMAP · cosine heatmap · value distribution · model-comparison figures |
| `report.py` | samples real corpus chunks, benchmarks every available model, writes report + figures |

### Persistence layout
```
knowledge_base/derived/<resource_id>/embeddings/
    <model>.jsonl            {chunk_id, vector}
    <model>.manifest.json    {model, version, dim, count, created_at, updated_at}
knowledge_base/derived/_embedding_cache/<version>.jsonl
```
Multiple models coexist per resource (needed for benchmarking); the chunk's
`ChunkMetadata.embedding_*` reserved fields (Stage 3) are now filled — no schema
change.

## Models supported
| key | HF model | dim | notes |
|---|---|---|---|
| `hashing` | — | 384 | dependency-free default; always available |
| `e5-small` | intfloat/multilingual-e5-small | 384 | production default (multilingual); uses query/passage prefixes |
| `bge-m3` | BAAI/bge-m3 | 1024 | highest-quality tier (~2.3 GB) |
| `minilm` | paraphrase-multilingual-MiniLM-L12-v2 | 384 | fast multilingual baseline |

Transformer models require the optional extra `pip install -e ".[models]"`
(sentence-transformers + torch); the code works without it via the hashing
backend (`transformer_available()` gates selection).

## CLI
```powershell
ala embed --all                       # embed every chunked resource (default model)
ala embed --resource <id>             # embed one resource
ala embed --model e5-small --all      # choose a model
ala embed --benchmark [--models hashing,minilm,e5-small,bge-m3] [--sample 300]
```

## Validation

Unit + integration tests in `tests/test_embedding.py` (determinism, normalization,
semantic ordering, factory, cache persistence, store round-trip + manifest,
benchmark metrics, full service → status `embedded` + incremental no-op).

### Benchmark (300 real corpus chunks, 7 courses; CPU sandbox)
Timing excludes one-time model load (warmup pass); `nn_purity` = fraction of
chunks whose nearest neighbour shares the same resource (rank-based quality,
robust to each model's cosine scale).

| model | dim | texts/s | query_ms | coherence | **nn_purity** |
|---|---|---|---|---|---|
| hashing | 384 | 48.9 | 3.6 | 0.253 | 0.697 |
| minilm | 384 | 53.5 | 44.1 | 0.285 | 0.627 |
| **e5-small** | 384 | 21.5 | 72.8 | 0.072 | **0.740** |

**Findings:**
- **e5-small has the best retrieval quality** (nn_purity 0.74) → the right
  production default (matches V3). Its low *coherence gap* is a metric artifact
  (e5 packs vectors into a narrow high-cosine band); nn_purity is the fair signal.
- **hashing** is fast, zero-dependency, and surprisingly strong (0.70) on this
  English technical corpus with heavy shared vocabulary → a solid offline fallback.
- **MiniLM** is the fastest transformer but lowest quality here.
- Latencies reflect a **CPU-only sandbox**; a GPU is 1–2 orders faster. bge-m3
  (2.3 GB) is registered/wired but not downloaded in this run.

### Figures (`reports/stage4_embedding/figures/`)
`model_comparison.png` + per-model `pca_*`, `tsne_*`, `cosine_*`, `dist_*` (13
total). The e5-small t-SNE shows clean course-level clustering — semantic
structure confirmed on the real corpus.
