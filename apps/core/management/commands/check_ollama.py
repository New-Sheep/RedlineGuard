"""Probe local Ollama: GET /api/tags and print installed models."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.ollama_engine import OllamaEngine, OllamaEngineError


class Command(BaseCommand):
    help = "Check that Ollama is reachable and list installed models."

    def handle(self, *args, **options):
        host = getattr(settings, "OLLAMA_HOST", "http://127.0.0.1:11434")
        model = getattr(settings, "OLLAMA_MODEL", "llama3.1:8b")
        engine = OllamaEngine(host=host, model=model, timeout_s=10.0)
        self.stdout.write(f"Ollama host: {host}")
        self.stdout.write(f"Configured model: {model}")
        try:
            names = engine.list_tags()
        except OllamaEngineError as exc:
            self.stderr.write(self.style.ERROR(f"Ollama unreachable: {exc}"))
            raise SystemExit(1) from exc

        if not names:
            self.stdout.write(self.style.WARNING("No models installed (ollama pull <name>)."))
            return

        self.stdout.write(self.style.SUCCESS(f"Installed models ({len(names)}):"))
        for n in names:
            mark = " ← configured" if n == model or n.startswith(f"{model}:") or model in n else ""
            self.stdout.write(f"  - {n}{mark}")

        if not any(model == n or model in n or n.startswith(model) for n in names):
            self.stdout.write(
                self.style.WARNING(
                    f"Configured OLLAMA_MODEL={model!r} not found in tags — "
                    f"pull it or set OLLAMA_MODEL to one of the names above."
                )
            )
