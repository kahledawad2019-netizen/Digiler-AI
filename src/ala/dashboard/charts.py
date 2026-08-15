"""Tiny dependency-free SVG chart helpers for the self-contained HTML dashboard."""

from __future__ import annotations

import html as _h


def mastery_color(v: float) -> str:
    if v < 0.4:
        return "#C44E52"
    if v < 0.7:
        return "#DD8452"
    return "#55A868"


def hbars(items: list[tuple[str, float]], *, width: int = 420, maxv: float = 1.0,
          colorer=None, fmt="{:.2f}") -> str:
    """Horizontal bar chart: items = [(label, value)]."""
    rowh, pad, lblw = 26, 6, 150
    h = max(1, len(items)) * rowh + pad
    bw = width - lblw - 60
    rows = []
    for i, (label, v) in enumerate(items):
        y = i * rowh + pad
        w = max(2, int(bw * min(1.0, v / maxv))) if maxv else 2
        col = (colorer or (lambda _v: "#4C72B0"))(v)
        rows.append(
            f'<text x="0" y="{y+16}" class="cl">{_h.escape(str(label)[:24])}</text>'
            f'<rect x="{lblw}" y="{y+4}" width="{w}" height="16" rx="3" fill="{col}">'
            f'<title>{_h.escape(str(label))}: {fmt.format(v)}</title></rect>'
            f'<text x="{lblw+w+5}" y="{y+16}" class="cv">{fmt.format(v)}</text>')
    return f'<svg width="{width}" height="{h}" viewBox="0 0 {width} {h}">{"".join(rows)}</svg>'


def line(points: list[float], *, width: int = 440, height: int = 160,
         color: str = "#8172B3", threshold: float | None = None) -> str:
    if not points:
        return '<svg width="1" height="1"></svg>'
    pad = 24
    n = len(points)
    xs = [pad + (width - 2 * pad) * (i / max(1, n - 1)) for i in range(n)]
    ys = [height - pad - (height - 2 * pad) * min(1.0, max(0.0, v)) for v in points]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}">'
                   f'<title>{v:.2f}</title></circle>' for x, y, v in zip(xs, ys, points))
    thr = ""
    if threshold is not None:
        ty = height - pad - (height - 2 * pad) * threshold
        thr = f'<line x1="{pad}" y1="{ty:.1f}" x2="{width-pad}" y2="{ty:.1f}" ' \
              f'stroke="#bbb" stroke-dasharray="4"/>'
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'{thr}<path d="{path}" fill="none" stroke="{color}" stroke-width="2"/>{dots}</svg>')


def heatmap(cells: list[dict], *, cols: int = 10, cell: int = 34) -> str:
    """Grid of concept mastery cells (red→green), hover shows the concept."""
    if not cells:
        return '<svg width="1" height="1"></svg>'
    rows = (len(cells) + cols - 1) // cols
    w, h = cols * cell + 2, rows * cell + 2
    rects = []
    for i, c in enumerate(cells):
        x, y = (i % cols) * cell + 1, (i // cols) * cell + 1
        rects.append(
            f'<rect x="{x}" y="{y}" width="{cell-3}" height="{cell-3}" rx="4" '
            f'fill="{mastery_color(c["mastery"])}">'
            f'<title>{_h.escape(str(c["concept"]))} ({c.get("domain","")}): {c["mastery"]:.2f}</title>'
            f'</rect>')
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{"".join(rects)}</svg>'


def donut(value: float, *, size: int = 130, color: str = "#55A868") -> str:
    import math
    r = size / 2 - 12
    cx = cy = size / 2
    frac = min(1.0, max(0.0, value))
    circ = 2 * math.pi * r
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#eee" stroke-width="12"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="12" '
            f'stroke-dasharray="{circ*frac:.1f} {circ:.1f}" stroke-linecap="round" '
            f'transform="rotate(-90 {cx} {cy})"/>'
            f'<text x="{cx}" y="{cy+6}" text-anchor="middle" class="donut">{value*100:.0f}%</text></svg>')
