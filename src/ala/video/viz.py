"""Stage 16 — Video Adapter figures, from real benchmark output."""

from __future__ import annotations

from pathlib import Path

_C = {"blue": "#4C72B0", "green": "#55A868", "orange": "#DD8452", "purple": "#8172B3",
      "grey": "#937860", "red": "#C44E52"}


def render_all(payload: dict, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _pipeline(plt, figs)
    _coverage(plt, payload, figs)
    _timeline(plt, payload, figs)
    _ingest(plt, payload, figs)


def _pipeline(plt, figs):
    steps = ["Video\n(YT/MP4)", "Speech→Text\n/ captions", "Frame OCR\n(slides)", "Scene\nsegmentation",
             "Timestamp\nblocks", "DIR +\nChunking", "Embed +\nQdrant/BM25", "Concept\nGraph", "GraphRAG\n(m:ss cite)"]
    colors = [_C["grey"], _C["blue"], _C["orange"], _C["purple"], _C["purple"],
              _C["green"], _C["blue"], _C["purple"], _C["green"]]
    fig, ax = plt.subplots(figsize=(16, 3))
    for i, (s, c) in enumerate(zip(steps, colors)):
        ax.add_patch(plt.Rectangle((i * 1.75, 0), 1.45, 1.3, color=c, alpha=0.9))
        ax.text(i * 1.75 + 0.72, 0.65, s, ha="center", va="center", color="white",
                fontsize=8, fontweight="bold")
        if i < len(steps) - 1:
            ax.annotate("", xy=(i * 1.75 + 1.72, 0.65), xytext=(i * 1.75 + 1.45, 0.65),
                        arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.text(0, -0.45, "Timestamps (t_start) are carried by every block → chunk → payload → citation, unchanged.",
            fontsize=9, style="italic")
    ax.set_xlim(-0.2, len(steps) * 1.75); ax.set_ylim(-0.8, 1.5); ax.axis("off")
    ax.set_title("Video Adapter pipeline (Stage 16)", fontsize=13)
    fig.tight_layout(); fig.savefig(figs / "video_pipeline.png", dpi=130); plt.close(fig)


def _coverage(plt, p, figs):
    cov = p["timestamp_coverage"]
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(["with timestamp", "without"], [cov, round(1 - cov, 4)], color=[_C["green"], _C["red"]])
    ax.set_ylim(0, 1.08)
    ax.set_title(f"Timestamp coverage of video child chunks (n={p['n_children']})")
    for i, v in enumerate([cov, round(1 - cov, 4)]):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "timestamp_coverage.png", dpi=130); plt.close(fig)


def _timeline(plt, p, figs):
    segs = p["segments"][:40]
    fig, ax = plt.subplots(figsize=(12, 4.5))
    for i, s in enumerate(segs):
        ax.barh(0, s["end"] - s["start"], left=s["start"], height=0.5,
                color=_C["blue"] if i % 2 == 0 else _C["purple"], alpha=0.85)
    rt = p["retrieval"]["returned_timestamp"]
    if rt is not None:
        ax.axvline(rt, color=_C["red"], lw=2, label=f"retrieved @ {p['retrieval']['clock']}")
        ax.legend()
    ax.set_yticks([]); ax.set_xlabel("seconds")
    ax.set_title(f"Transcript segment timeline ({len(p['segments'])} cues, {p['duration_s']} s)")
    fig.tight_layout(); fig.savefig(figs / "segment_timeline.png", dpi=130); plt.close(fig)


def _ingest(plt, p, figs):
    t = p["timings_ms"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(list(t.keys()), list(t.values()), color=_C["purple"])
    ax.set_title(f"Video ingest per-stage latency (total {p['total_ms']} ms)"); ax.set_ylabel("ms")
    for i, v in enumerate(t.values()):
        ax.text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout(); fig.savefig(figs / "ingest_timeline.png", dpi=130); plt.close(fig)
