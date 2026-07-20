"""Split contract text into offset-aware segments for semantic retrieve."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    text: str
    start: int
    end: int


_HEADING = re.compile(r"^[A-Z0-9][A-Z0-9 \-/&]{2,80}$")
_MIN_LEN = 40
_MAX_LEN = 1200


def segment_paragraphs(text: str) -> list[Segment]:
    """Split on blank lines; also break on short ALL-CAPS heading lines."""
    if not (text or "").strip():
        return []

    parts: list[Segment] = []
    chunks = re.split(r"\n\s*\n+", text)
    cursor = 0
    for chunk in chunks:
        idx = text.find(chunk, cursor)
        if idx < 0:
            idx = cursor
        start = idx
        end = idx + len(chunk)
        cursor = end
        _emit_chunk(text, chunk, start, parts)

    if not parts:
        step = 350
        for i in range(0, len(text), step):
            piece = text[i : i + 500].strip()
            if len(piece) >= _MIN_LEN:
                parts.append(
                    Segment(text=piece[:_MAX_LEN], start=i, end=min(len(text), i + 500))
                )
    return parts


def _emit_chunk(full: str, chunk: str, base: int, out: list[Segment]) -> None:
    lines = chunk.split("\n")
    buf: list[str] = []
    buf_start = base
    pos = base

    def flush() -> None:
        nonlocal buf, buf_start
        if not buf:
            return
        joined = "\n".join(buf).strip()
        if len(joined) >= _MIN_LEN:
            end = buf_start + len("\n".join(buf))
            out.append(
                Segment(text=joined[:_MAX_LEN], start=buf_start, end=min(len(full), end))
            )
        buf = []

    for line in lines:
        line_start = pos
        pos += len(line) + 1
        stripped = line.strip()
        if stripped and _HEADING.match(stripped) and len(stripped) < 90:
            flush()
            buf_start = line_start + len(line) + 1
            continue
        if not buf:
            buf_start = line_start
        buf.append(line)
        if sum(len(x) for x in buf) > _MAX_LEN:
            flush()
            buf_start = pos
    flush()
