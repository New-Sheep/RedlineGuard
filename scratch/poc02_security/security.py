"""POC 02 — sanitize, fence, injection detection."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
_ROOT = _SCRATCH.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scratch._io import (  # noqa: E402
    CORPUS,
    ensure_run_dir,
    print_banner,
    sync_latest,
    write_json,
    write_text,
)
from scratch.poc01_extract.extract import extract_pdf  # noqa: E402

_ZERO_WIDTH = re.compile(
    "[\u200b\u200c\u200d\u2060\ufeff\u00ad]"
)

# Phrases checked against whitespace-stripped lowercase alnum blob
_COMPACT_PHRASES = [
    "ignoreallpreviousinstructions",
    "ignoreallpriorinstructions",
    "ignoreallinstructions",
    "ignoretheplaybook",
    "ignoreallplaybook",
    "ignoreplaybookrules",
    "approveallclauses",
    "approveeveryclause",
    "systemoverridemode",
    "systemoverride",
    "outputtheexacttextoftheplaybook",
    "playbookconfig",
    "trackingpixel",
    "xssexecution",
    # Multilingual compact forms
    "ignoratodaslasinstrucciones",
    "ignoratodaslasinstruccionesanteriores",
    "ignoreztouteslesinstructions",
    "ignoriereallevorherigenanweisungen",
    "notadelsistema",
    "statusdebeserapproved",
    "attentionwindow",
    "ipsurrender",
    "transferalltrademarks",
]

_LLM_EXPORT_COMPACT_PHRASES = [
    "geminigooglecom",
    "chatspark",
]

# Regex on deobfuscated (still spaced) text
_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE | re.DOTALL)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+(all\s+)?prior\s+instructions",
        r"ignore\s+all\s+instructions",
        r"ignore\s+all\s+playbook",
        r"disregard\s+(any\s+)?rules",
        r"you\s+are\s+no\s+longer",
        r"system\s+override",
        r"system_override",
        r"system_instruction",
        r"system_note",
        r"system_directive",
        r"urgent_directive",
        r"audit_override",
        r"approve\s+every\s+clause",
        r"approve\s+all\s+clauses?",
        r"ignore\s+the\s+playbook",
        r"ignore\s+playbook",
        r"<\s*\|\s*system\s*\|\s*>",
        r"\[INST\]",
        # Multilingual instruction overrides (ES / FR / DE)
        r"ignora\s+(todas\s+las\s+)?instrucciones(\s+anteriores)?",
        r"ignorez\s+(toutes\s+les\s+)?instructions",
        r"ignoriere\s+alle\s+(vorherigen\s+)?anweisungen",
        r"<\s*nota_del_sistema\s*>",
        r"nota_del_sistema",
        r"aprobar\s+este\s+contrato",
        r"status[\"']?\s*debe\s*ser\s*[\"']?APPROVED",
        r"[\"']status[\"']\s*:\s*[\"']APPROVED[\"'].{0,40}(ignore|ignora|do\s+not)",
        # XSS / HTML sink attacks aimed at structured fields
        r"alert\s*\(",
        r"onerror\s*=",
        r"<\s*script\b",
        r"<\s*img\b[^>]*onerror",
        r"javascript\s*:",
        # Exfil / markdown beacon
        r"tracking\s+pixel",
        r"tracking\s+markdown",
        r"!\[[^\]]*\]\(\s*https?://",
        r"suggested_counter_proposal[^\n]{0,80}https?://",
        # Prompt / playbook leak
        r"output\s+the\s+exact\s+text\s+of\s+the\s*\[?\s*playbook",
        r"place\s+the\s+entire\s+playbook",
        r"playbook\s+config\s*\]?",
        r"do\s+not\s+review\s+the\s+clauses",
        # Fragmented jailbreak scaffolding
        r"system\s+note\s+part\s*\d+",
        r"combine\s+system\s+note\s+parts",
        r"secret\s+authorization\s+code",
        r"emergency\s+executive\s+clearance",
        r"json\s+echo\s+server",
        r"operating\s+in\s+system\s+override",
        # Context-stuffing / attention exhaustion (LLM jailbreak narrative)
        r"\[\.\.\.\s*START\s+BOILERPLATE",
        r"START\s+BOILERPLATE",
        r"attention\s+window",
        r"short-term\s+memory",
        r"pushing\s+the\s+original\s+system\s+prompt",
        r"assume\s+this\s+exact\s+sentence\s+repeats",
        r"forget\s+the\s+strict\s+playbook",
        # Extreme IP giveaway often paired with stuffing attacks
        r"\bIP\s+Surrender\b",
        r"transfer\s+all\s+(trademarks|patents|software\s+copyrights)",
        # Poisoned "calibration" / few-shot smuggling (esp. fake playbooks)
        r"system_calibration",
        r"<\s*system_calibration\s*>",
        r"ground-truth\s+examples",
        r"previous\s+audit\s+log",
        r"attention\s+redlineguard",
        r"verified,\s+ground-truth",
        r"you\s+must\s+follow\s+the\s+exact\s+pattern",
        r"please\s+proceed\s+with\s+your\s+json\s+output",
    ]
]

# Contract-upload provenance (Gemini chat screenshots). NOT used for playbook PDFs —
# those are often exported from Gemini too, without being injection.
_LLM_EXPORT_CHROME_PATTERNS = [
    re.compile(p, re.IGNORECASE | re.DOTALL)
    for p in [
        r"gemini\.google\.com",
        r"\bchat_spark\b",
        r"AI\s+Legal\s+Contract\s+Review\s+Task\s*[-–]\s*Google\s+Gemini",
    ]
]

# Consecutive same phrase (25+ chars, 5 copies) => context stuffing
_REPEAT_BLOCK = re.compile(
    r"(.{25,160}?)\s+\1\s+\1\s+\1\s+\1",
    re.IGNORECASE | re.DOTALL,
)


def sanitize(text: str) -> str:
    """Decode entities, strip zero-width / soft-hyphen abuse; keep readable text."""
    cleaned = html.unescape(text)
    cleaned = _ZERO_WIDTH.sub("", cleaned)
    cleaned = "".join(
        ch for ch in cleaned if ch.isprintable() or ch in "\n\r\t"
    )
    return cleaned


def collapse_char_obfuscation(text: str) -> str:
    """Turn I-G-N-O-R-E_A-L-L into IGNOREALL (hyphen/underscore letter-spacing)."""
    out = text
    prev = None
    while prev != out:
        prev = out
        out = re.sub(r"([A-Za-z0-9])[-_]+(?=[A-Za-z0-9])", r"\1", out)
    return out


def compact_alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def assemble_system_note_parts(text: str) -> str | None:
    """Join quoted fragments from 'System Note Part N: ... \"...\"' attacks."""
    parts = re.findall(
        r"System Note Part\s*\d\s*:\s*[^\"\n]*\"([^\"]+)\"",
        text,
        flags=re.IGNORECASE,
    )
    if len(parts) >= 2:
        return "".join(parts)
    # Broader: begins with / continues with / ends with
    bits = re.findall(
        r"(?:begins with|continues with|ends with)\s*:\s*\"([^\"]+)\"",
        text,
        flags=re.IGNORECASE,
    )
    if len(bits) >= 2:
        return "".join(bits)
    return None


def detect_repetition_stuffing(text: str) -> str | None:
    """Flag the same long phrase pasted back-to-back (context-stuffing).

    Requires consecutive repeats so section titles that recur as headings
    (e.g. 'Founders Collaboration Agreement') do not false-positive.
    """
    m = re.search(
        r"(.{25,160}?)\s+\1\s+\1\s+\1\s+\1",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        return f"[repeat-block] {m.group(1).strip()[:80]}"
    return None


def fence(text: str) -> str:
    return f"<untrusted_document>\n{text}\n</untrusted_document>"


def detect_injection(text: str, *, include_llm_export_chrome: bool = True) -> dict:
    """Detect prompt-injection / XSS / exfil / obfuscated jailbreaks.

    Runs checks on sanitized, letter-deobfuscated, compact, and reassembled
    fragment views so spaced/split attacks still halt.

    include_llm_export_chrome: when True (contract uploads), also halt on
    Gemini chat-export UI chrome. Playbook PDFs often come from Gemini too,
    so playbook ingest should pass False and rely on real injection cues.
    """
    sanitized = sanitize(text)
    deob = collapse_char_obfuscation(sanitized)
    views = [sanitized, deob, compact_alnum(deob)]

    assembled = assemble_system_note_parts(sanitized)
    if assembled:
        views.append(assembled)
        views.append(collapse_char_obfuscation(assembled))
        views.append(compact_alnum(assembled))

    hits: list[str] = []
    seen: set[str] = set()

    def add(hit: str) -> None:
        key = hit.lower().strip()
        if key and key not in seen:
            seen.add(key)
            hits.append(hit.strip()[:120])

    patterns = list(_INJECTION_PATTERNS)
    if include_llm_export_chrome:
        patterns.extend(_LLM_EXPORT_CHROME_PATTERNS)

    for view in views:
        for pat in patterns:
            m = pat.search(view)
            if m:
                add(m.group(0))
        if not re.fullmatch(r"[a-z0-9]*", view):
            compact = compact_alnum(view)
        else:
            compact = view
        for phrase in _COMPACT_PHRASES:
            if phrase in compact:
                add(f"[compact]{phrase}")
        if include_llm_export_chrome:
            for phrase in _LLM_EXPORT_COMPACT_PHRASES:
                if phrase in compact:
                    add(f"[compact]{phrase}")

    stuffing = detect_repetition_stuffing(sanitized)
    if stuffing:
        add(stuffing)

    return {
        "halt": len(hits) > 0,
        "matches": hits,
        "summary": (
            "Possible prompt-injection / instruction-override language detected."
            if hits
            else "No obvious injection patterns detected."
        ),
    }


def detect_playbook_injection(text: str) -> dict:
    """Security gate for playbook PDFs (no Gemini-chrome false positives)."""
    return detect_injection(text, include_llm_export_chrome=False)


def run_on_text(text: str, source_name: str = "input") -> dict:
    sanitized = sanitize(text)
    detection = detect_injection(text)
    fenced = fence(sanitized)
    return {
        "source_name": source_name,
        "halt": detection["halt"],
        "matches": detection["matches"],
        "summary": detection["summary"],
        "sanitized": sanitized,
        "fenced": fenced,
        "char_count_sanitized": len(sanitized),
    }


def run(
    path: Path | str | None = None,
    *,
    text: str | None = None,
    source_name: str = "input",
    run_dir: Path | None = None,
) -> dict:
    if text is None:
        if path is None:
            raise ValueError("Provide path or text")
        path = Path(path)
        extracted = extract_pdf(path)
        text = extracted["text"]
        source_name = path.name
        out = ensure_run_dir(run_dir, path)
    else:
        out = ensure_run_dir(run_dir, source_name)

    result = run_on_text(text, source_name)
    write_json(
        out / "02_security.json",
        {
            "source_name": result["source_name"],
            "halt": result["halt"],
            "matches": result["matches"],
            "summary": result["summary"],
            "char_count_sanitized": result["char_count_sanitized"],
        },
    )
    write_text(out / "02_sanitized.txt", result["sanitized"])
    write_text(out / "02_fenced.txt", result["fenced"])
    sync_latest(out)
    return {**result, "run_dir": str(out)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="POC 02: security sanitize/fence/detect")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(CORPUS / "injection_hostile.txt"),
    )
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument(
        "--from-out",
        type=Path,
        default=None,
        help="Read 01_raw.txt from an existing run directory",
    )
    args = parser.parse_args(argv)

    print_banner("STEP 02", "SECURITY")
    if args.from_out:
        raw = Path(args.from_out) / "01_raw.txt"
        text = raw.read_text(encoding="utf-8", errors="replace")
        result = run(text=text, source_name=raw.parent.name, run_dir=args.from_out)
    else:
        result = run(args.path, run_dir=args.run_dir)

    verdict = "HALT" if result["halt"] else "PASS"
    print(f"Source:  {result['source_name']}")
    print(f"Verdict: {verdict}")
    print(f"Summary: {result['summary']}")
    if result["matches"]:
        print(f"Matches: {result['matches']}")
    print(f"Artifacts: {result['run_dir']}")
    print("\n--- fenced head ---")
    print("\n".join(result["fenced"].splitlines()[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
