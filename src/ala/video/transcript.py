"""Transcript I/O — parse WebVTT / SRT / JSON captions into VideoCues (stdlib only).

YouTube and recorded-lecture captions are standard WebVTT/SRT; this parses them
without any third-party dependency, so the timestamped path works fully offline.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ala.video.models import VideoCue, VideoInfo, VideoTranscript

_TS = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})")
_TS_SHORT = re.compile(r"(\d{1,2}):(\d{2})[.,](\d{1,3})")
_ARROW = re.compile(r"-->")
_TAG = re.compile(r"<[^>]+>")


def _to_seconds(ts: str) -> float | None:
    m = _TS.search(ts)
    if m:
        h, mi, s, ms = m.groups()
        return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000
    m = _TS_SHORT.search(ts)
    if m:
        mi, s, ms = m.groups()
        return int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000
    return None


def parse_captions(text: str) -> list[VideoCue]:
    """Parse WebVTT or SRT (both use ``start --> end`` timing lines)."""
    cues: list[VideoCue] = []
    start = end = None
    buf: list[str] = []

    def flush():
        nonlocal start, end, buf
        if start is not None and buf:
            body = _TAG.sub("", " ".join(buf)).strip()
            if body:
                cues.append(VideoCue(start=start, end=end if end is not None else start, text=body))
        start = end = None
        buf = []

    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if _ARROW.search(line):
            flush()
            a, _, b = line.partition("-->")
            start, end = _to_seconds(a), _to_seconds(b)
        elif not line or line.upper().startswith(("WEBVTT", "NOTE")) or line.isdigit():
            if not line:
                flush()
        elif start is not None:
            buf.append(line)
    flush()
    # merge duplicate/rolling caption lines (YouTube auto-captions repeat)
    merged: list[VideoCue] = []
    for c in cues:
        if merged and c.text.startswith(merged[-1].text[:20]) and c.start - merged[-1].end < 0.5:
            merged[-1] = VideoCue(merged[-1].start, c.end, c.text, c.kind)
        elif not (merged and merged[-1].text == c.text):
            merged.append(c)
    return merged


def parse_json(text: str) -> list[VideoCue]:
    """Parse a JSON transcript: [{start,end,text}] or whisper-style {segments:[…]}."""
    data = json.loads(text)
    segs = data.get("segments", data) if isinstance(data, dict) else data
    out: list[VideoCue] = []
    for s in segs:
        st = float(s.get("start", 0.0))
        out.append(VideoCue(start=st, end=float(s.get("end", st)),
                            text=str(s.get("text", "")).strip()))
    return [c for c in out if c.text]


def load_transcript(path: str | Path, info: VideoInfo | None = None) -> VideoTranscript:
    p = Path(path)
    raw = p.read_text(encoding="utf-8", errors="replace")
    cues = parse_json(raw) if p.suffix.lower() == ".json" else parse_captions(raw)
    info = info or VideoInfo(title=p.stem.replace("-", " ").title(), source=str(p), kind="caption")
    if not info.duration:
        info.duration = max((c.end for c in cues), default=0.0)
    return VideoTranscript(info=info, cues=cues)


def write_vtt(transcript: VideoTranscript) -> str:
    """Serialise cues back to WebVTT (used when a backend produces raw segments)."""
    def clock(sec: float) -> str:
        h, r = divmod(sec, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"
    lines = ["WEBVTT", ""]
    for c in transcript.cues:
        lines += [f"{clock(c.start)} --> {clock(c.end)}", c.text, ""]
    return "\n".join(lines)
