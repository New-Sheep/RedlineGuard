"""Redirect unauthenticated users when REQUIRE_AUTH is on."""

from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect

from apps.accounts.models import ensure_profile


OPEN_PREFIXES = (
    "/login/",
    "/logout/",
    "/admin/login/",
    "/static/",
    "/media/",
    "/trust/",  # public explainability story
)

# While onboarding is incomplete, still allow Journey A paths from the wizard
ONBOARDING_ALLOW = (
    "/onboarding/",
    "/playbook",
    "/contracts",
    "/memory",
    "/help",
    "/trust",
    "/lab/",
    "/history",
    "/audit",
    "/logout",
    "/api/",
    "/static/",
    "/media/",
)


class RequireAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "REQUIRE_AUTH", True):
            return self.get_response(request)

        path = request.path or "/"
        if any(path.startswith(p) for p in OPEN_PREFIXES):
            return self.get_response(request)
        # Django admin uses its own auth
        if path.startswith("/admin/"):
            return self.get_response(request)

        if not request.user.is_authenticated:
            if path.startswith("/api/") or "application/json" in (
                request.headers.get("Accept") or ""
            ):
                return JsonResponse({"error": "authentication required"}, status=401)
            login = getattr(settings, "LOGIN_URL", "/login/")
            return redirect(f"{login}?next={request.get_full_path()}")

        # Soft nudge: incomplete onboarding → wizard, unless already on a Journey A path
        allowed = path == "/" or any(path.startswith(p) for p in ONBOARDING_ALLOW)
        if not allowed:
            try:
                profile = ensure_profile(request.user)
                if not profile.onboarding_complete:
                    return redirect("/onboarding/")
            except Exception:
                pass

        return self.get_response(request)
