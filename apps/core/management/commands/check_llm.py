"""Probe Fake / Ollama / cloud HTTP LLM providers (keys never printed)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Smoke-test configured LLM providers (DeepSeek / Moonshot / NVIDIA / Ollama)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--draft",
            action="store_true",
            help="Also run suggest_draft via get_llm_client()",
        )

    def handle(self, *args, **options):
        from dotenv import load_dotenv

        load_dotenv(Path(".").resolve() / ".env")

        fake = os.environ.get("FAKE_LLM", "1")
        provider = os.environ.get("LLM_PROVIDER", "auto")
        self.stdout.write(f"FAKE_LLM={fake} LLM_PROVIDER={provider}")

        from apps.core.llm_providers import _PRESETS, resolve_provider_config

        for name, (key_env, base, model) in _PRESETS.items():
            key = (os.environ.get(key_env) or "").strip()
            masked = (
                f"{key[:4]}…{key[-4:]} (len={len(key)})"
                if len(key) > 12
                else ("set" if key else "MISSING")
            )
            self.stdout.write(f"  {name}: {key_env}={masked} default_model={model}")

        self.stdout.write("")
        self.stdout.write("Live ping (OpenAI-compatible /chat/completions)…")
        import urllib.error
        import urllib.request

        results = []
        for name, (key_env, base, model) in _PRESETS.items():
            key = (os.environ.get(key_env) or "").strip()
            if not key or key in ("<>",):
                self.stdout.write(self.style.WARNING(f"  SKIP {name}: no key"))
                continue
            base_url = os.environ.get(f"{name.upper()}_BASE_URL", base).rstrip("/")
            model_id = os.environ.get(f"{name.upper()}_MODEL", model)
            payload = {
                "model": model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": 'Reply with JSON only: {"ok":true}',
                    }
                ],
                "max_tokens": 32,
                "temperature": 0,
            }
            req = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    body = json.loads(resp.read().decode())
                content = body["choices"][0]["message"]["content"][:120]
                self.stdout.write(
                    self.style.SUCCESS(f"  OK   {name} ({model_id}): {content!r}")
                )
                results.append((name, True))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:180]
                self.stdout.write(
                    self.style.ERROR(f"  FAIL {name} HTTP {exc.code}: {detail}")
                )
                results.append((name, False))
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f"  FAIL {name}: {exc}"))
                results.append((name, False))

        if options["draft"]:
            self.stdout.write("")
            self.stdout.write("get_llm_client().suggest_draft …")
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            import django

            django.setup()
            from apps.core.llm import get_llm_client

            client = get_llm_client()
            self.stdout.write(f"  client={type(client).__name__}")
            sug = client.suggest_draft(
                playbook_rule={
                    "id": "governing_law",
                    "preferred": "England and Wales",
                    "hard_ceiling": "England and Wales or Delaware",
                    "fallback_text": (
                        "This Agreement shall be governed by the laws of England and Wales."
                    ),
                },
                finding={
                    "playbook_rule_id": "governing_law",
                    "status": "needs_human",
                    "deviation_reason": "California law",
                    "clause_name": "Governing Law",
                },
                fenced_contract_excerpt=(
                    "<untrusted_document>Governed by the laws of California."
                    "</untrusted_document>"
                ),
            )
            self.stdout.write(self.style.SUCCESS(f"  draft={sug.draft_text[:200]!r}"))
            self.stdout.write(f"  rationale={sug.rationale[:160]!r}")

        ok = sum(1 for _, good in results if good)
        self.stdout.write("")
        self.stdout.write(f"Providers OK: {ok}/{len(results)}")
        if fake.strip() in ("0", "false", "False"):
            cfg = resolve_provider_config(provider)
            if cfg:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Active cloud path: {cfg.name} -> {cfg.model} @ {cfg.base_url}"
                    )
                )
            else:
                self.stdout.write("Active path: Ollama (no cloud provider resolved)")
        else:
            self.stdout.write(
                "FAKE_LLM=1 -> drafts/judge use Fake (set FAKE_LLM=0 for real)"
            )
