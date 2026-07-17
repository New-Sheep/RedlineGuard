"""Re-run malicious corpus through security + full pipeline."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scratch.poc01_extract.extract import extract_pdf
from scratch.poc02_security.security import detect_injection

cli = importlib.import_module("scratch.05_dry_run_cli")
root = ROOT / "data" / "malicious_corpus"

print("FILE | HALT | sample matches")
failed = []
paths = sorted(root.glob("*.pdf"), key=lambda x: x.name)
for p in paths:
    text = extract_pdf(p)["text"]
    d = detect_injection(text)
    cli.run_pipeline(p)
    matches = d["matches"][:4]
    print(f"{p.name} | halt={d['halt']} | {matches}")
    if not d["halt"]:
        failed.append(p.name)

print("---")
if failed:
    print("STILL PASSING:", failed)
    sys.exit(1)
print(f"ALL {len(paths)} HALTED")
