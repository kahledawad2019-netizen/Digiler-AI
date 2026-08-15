"""Embedding visualizations (saved as PNG figures).

PCA / t-SNE / UMAP projections, cosine-similarity heatmaps, value distribution,
and a model-comparison chart. matplotlib/scikit-learn are imported lazily so the
module imports without them; UMAP is optional (falls back gracefully). All
functions return the saved path.
"""

from __future__ import annotations

from pathlib import Path


def _plt():
    import matplotlib
    matplotlib.use("Agg")           # headless
    import matplotlib.pyplot as plt
    return plt


def _scatter(coords, labels, title, path: Path):
    plt = _plt()
    import numpy as np

    fig, ax = plt.subplots(figsize=(8, 6))
    labels = labels or ["all"] * len(coords)
    uniq = sorted(set(labels))
    cmap = plt.get_cmap("tab20")
    for i, lab in enumerate(uniq):
        idx = [j for j, l in enumerate(labels) if l == lab]
        pts = np.asarray(coords)[idx]
        ax.scatter(pts[:, 0], pts[:, 1], s=10, color=cmap(i % 20), label=str(lab), alpha=0.7)
    if len(uniq) <= 15:
        ax.legend(fontsize=7, markerscale=1.5, loc="best")
    ax.set_title(title)
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def pca_figure(vectors, labels, path: Path, title="Embedding PCA"):
    from sklearn.decomposition import PCA
    import numpy as np

    coords = PCA(n_components=2, random_state=0).fit_transform(np.asarray(vectors, "float32"))
    return _scatter(coords, labels, title, Path(path))


def tsne_figure(vectors, labels, path: Path, title="Embedding t-SNE"):
    from sklearn.manifold import TSNE
    import numpy as np

    arr = np.asarray(vectors, "float32")
    perplexity = max(5, min(30, (len(arr) - 1) // 3))
    coords = TSNE(n_components=2, random_state=0, perplexity=perplexity,
                  init="pca").fit_transform(arr)
    return _scatter(coords, labels, title, Path(path))


def umap_figure(vectors, labels, path: Path, title="Embedding UMAP"):
    try:
        import umap
    except ImportError:
        return None                 # optional dependency; skip cleanly
    import numpy as np

    coords = umap.UMAP(n_components=2, random_state=0).fit_transform(np.asarray(vectors, "float32"))
    return _scatter(coords, labels, title, Path(path))


def cosine_heatmap(vectors, labels, path: Path, title="Cosine similarity", cap=40):
    plt = _plt()
    import numpy as np

    arr = np.asarray(vectors, "float32")[:cap]
    sims = arr @ arr.T
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(sims, cmap="viridis", vmin=-1, vmax=1)
    fig.colorbar(im, ax=ax, fraction=0.046)
    ax.set_title(f"{title} (first {len(arr)} chunks)")
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def distribution_figure(vectors, path: Path, title="Embedding value distribution"):
    plt = _plt()
    import numpy as np

    arr = np.asarray(vectors, "float32")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    ax1.hist(arr.flatten(), bins=60, color="#4C72B0")
    ax1.set_title("Component values")
    ax2.hist(np.linalg.norm(arr, axis=1), bins=40, color="#55A868")
    ax2.set_title("Vector L2 norms")
    fig.suptitle(title)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def comparison_figure(results, path: Path, title="Embedding model comparison"):
    """Bar charts comparing throughput, query latency, dim, and coherence."""
    plt = _plt()

    models = [r.model_id for r in results]
    metrics = [
        ("texts/s (throughput)", [r.texts_per_s for r in results]),
        ("query latency (ms)", [r.query_latency_ms for r in results]),
        ("dimension", [r.dim for r in results]),
        ("NN purity (top-1 same-resource)", [(r.nn_purity or 0.0) for r in results]),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, (name, vals) in zip(axes.flat, metrics):
        ax.bar(models, vals, color="#4C72B0")
        ax.set_title(name)
        ax.tick_params(axis="x", labelrotation=20)
    fig.suptitle(title)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
