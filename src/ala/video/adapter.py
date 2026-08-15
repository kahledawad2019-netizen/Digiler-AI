"""VideoAdapter — obtain a timestamped transcript from a video source.

Sources: a local caption/transcript file (``.vtt``/``.srt``/``.json``), a local
media file (``.mp4``/… → ASR transcriber + optional slide OCR), or a YouTube URL
(captions/audio via yt-dlp — a guarded seam). Returns a ``VideoTranscript`` of
timestamped cues; the downstream ingest reuses the existing pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ala.video.models import VideoConfig, VideoInfo, VideoTranscript
from ala.video.ocr import make_ocr
from ala.video.transcriber import CaptionTranscriber, make_transcriber

log = logging.getLogger("ala.video.adapter")
_MEDIA = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4a", ".mp3", ".wav"}
_CAPTION = {".vtt", ".srt", ".json"}


class VideoAdapter:
    def __init__(self, config: VideoConfig | None = None, transcriber=None, ocr=None) -> None:
        self.config = config or VideoConfig()
        self.transcriber = transcriber or make_transcriber(self.config)
        self.ocr = ocr or make_ocr(self.config)

    def transcribe(self, source: str | Path, *, title: str | None = None) -> VideoTranscript:
        s = str(source)
        if s.startswith(("http://", "https://")):
            cues, kind, src = self._youtube(s), "youtube", s
        else:
            p = Path(source)
            kind = "caption" if p.suffix.lower() in _CAPTION else "mp4"
            cues = self.transcriber.transcribe(p)
            if p.suffix.lower() in _MEDIA:
                cues = cues + self.ocr.ocr(p)                 # slide text with timestamps
            src = str(p)
            title = title or p.stem.replace("-", " ").replace("_", " ").title()
        info = VideoInfo(title=title or "Video", source=src, kind=kind,
                         duration=max((c.end for c in cues), default=0.0),
                         language=self.config and "en")
        return VideoTranscript(info=info, cues=sorted(cues, key=lambda c: c.start))

    # ------------------------------------------------------------------ #
    def _youtube(self, url: str) -> list:
        """Fetch captions (preferred) or audio via yt-dlp — guarded optional dep."""
        try:
            import tempfile

            import yt_dlp
        except ImportError:
            log.warning("yt-dlp not installed; cannot fetch '%s' (install extras)", url)
            return []
        tmp = Path(tempfile.mkdtemp(prefix="ala_yt_"))
        opts = {"skip_download": True, "writesubtitles": True, "writeautomaticsub": True,
                "subtitlesformat": "vtt", "outtmpl": str(tmp / "%(id)s.%(ext)s"), "quiet": True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as exc:                              # network / unavailable
            log.warning("yt-dlp failed for %s: %s", url, exc)
            return []
        for vtt in tmp.glob("*.vtt"):
            return CaptionTranscriber().transcribe(vtt)
        return []
