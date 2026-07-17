"""Shared helpers for scratch POC step banners and artifact I/O."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(__file__).resolve().parent
OUT_ROOT = SCRATCH / "out"
CORPUS = ROOT / "data" / "scratch_corpus"
PLAYBOOK_PATH = ROOT / "data" / "playbook_config.json"
VECTOR_MEMORY = ROOT / "data" / "vector_memory"


def stem_of(path: Path | str) -> str:
    p = Path(path)
    return re.sub(r"[^\w\-.]+", "_", p.stem)[:80]


def new_run_dir(source: Path | str) -> Path:
    """Create scratch/out/<stem>/<utc_timestamp>/ (call sync_latest after writes)."""
    stem = stem_of(source)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = OUT_ROOT / stem / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def ensure_run_dir(run_dir: Path | None, source: Path | str) -> Path:
    if run_dir is not None:
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    return new_run_dir(source)


def sync_latest(run_dir: Path) -> None:
    """Refresh sibling latest/ from this run_dir after writing artifacts."""
    stem_dir = run_dir.parent
    latest = stem_dir / "latest"
    if latest.exists():
        if latest.is_dir() and not latest.is_symlink():
            shutil.rmtree(latest)
        else:
            latest.unlink(missing_ok=True)
    shutil.copytree(run_dir, latest, dirs_exist_ok=True)


def print_banner(step: str, title: str) -> None:
    line = "=" * 60
    print(f"\n{line}")
    print(f"=== {step}: {title} ===")
    print(line)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def write_skipped(run_dir: Path, step: str, reason: str) -> Path:
    path = run_dir / f"{step}_SKIPPED.md"
    body = (
        f"# Step {step} skipped\n\n"
        f"**Reason:** {reason}\n\n"
        "Later pipeline stages did not invent a review for this document.\n"
    )
    write_text(path, body)
    print(f"[SKIPPED] {step}: {reason}")
    return path
