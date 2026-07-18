from django.apps import AppConfig


class LearningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.learning"

    def ready(self) -> None:
        import os
        import sys

        # Skip during migrate / tests / runserver reloader child duplicate
        if "migrate" in sys.argv or "test" in sys.argv:
            return
        if os.environ.get("RUN_MAIN") == "false":
            return
        fake = os.environ.get("FAKE_EMBED", "0").strip() not in ("0", "false", "False")
        if fake:
            return
        # Warm MiniLM in a background thread so runserver stays responsive
        import threading

        def _warm() -> None:
            try:
                from apps.learning.services.memory import get_decision_store

                get_decision_store().embedder.embed(["redlineguard warmup"])
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_warm, daemon=True, name="embed-warmup").start()
