"""Stage 10.5 — concept extraction tests."""

from __future__ import annotations

from ala.graph.concepts import GENERIC_TERMS, ConceptExtractor, _candidate_phrases

LEX = [
    {"id": "cnn", "canonical": "Convolutional Neural Network",
     "aliases": ["cnn", "convolutional neural network", "convolutional network"], "domain": "deep-learning"},
    {"id": "foreign-key", "canonical": "Foreign Key",
     "aliases": ["foreign key", "fk"], "domain": "databases"},
    {"id": "gradient-descent", "canonical": "Gradient Descent",
     "aliases": ["gradient descent", "sgd"], "domain": "deep-learning"},
]


def test_lexicon_matching_with_acronyms():
    docs = {
        "r1": "We train a CNN. The convolutional neural network learns filters by gradient descent.",
        "r2": "A foreign key references a table. The FK enforces referential integrity.",
    }
    concepts = ConceptExtractor(LEX, embedder=None).extract(docs)
    by = {c.canonical: c for c in concepts}
    assert "Convolutional Neural Network" in by
    cnn = by["Convolutional Neural Network"]
    assert cnn.frequency >= 2 and "r1" in cnn.source_resources and cnn.seed is True
    assert "Foreign Key" in by and "r2" in by["Foreign Key"].source_resources
    assert "Gradient Descent" in by                       # matched in r1


def test_generic_single_words_never_become_concepts():
    docs = {"r1": "data example result chapter information model value",
            "r2": "data example result information"}
    concepts = ConceptExtractor(LEX, embedder=None, min_phrase_freq=1,
                                min_phrase_resources=1).extract(docs)
    labels = {c.canonical.lower() for c in concepts}
    assert not (labels & GENERIC_TERMS)                   # no generic term is a concept
    assert "data" not in labels and "example" not in labels


def test_candidate_phrases_multiword_clean_edges():
    phr = _candidate_phrases("the convolutional neural network uses gradient descent for data")
    assert "convolutional neural network" in phr and "gradient descent" in phr
    assert all(len(p.split()) >= 2 for p in phr)
    assert not any(p.split()[0] in {"the", "for"} or p.split()[-1] in {"the", "for", "uses"}
                   for p in phr)


def test_multiword_mining_with_embedder():
    from ala.retrieval.embedding import HashingEmbedder

    docs = {f"r{i}": "gradient descent optimizer and backpropagation training loop" for i in range(4)}
    ex = ConceptExtractor([LEX[0]], embedder=HashingEmbedder(dim=256),
                          min_phrase_freq=2, min_phrase_resources=3, domain_threshold=0.0)
    concepts = ex.extract(docs)
    assert concepts and all(c.frequency > 0 and c.source_resources for c in concepts)
    assert all(0.0 <= c.confidence <= 1.0 for c in concepts)
    assert all(len(c.canonical.split()) >= 2 for c in concepts if not c.seed)   # mined = multi-word
