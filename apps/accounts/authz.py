"""Auth roles + login helpers for RedlineGuard."""

from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect


def auth_required() -> bool:
    return bool(getattr(settings, "REQUIRE_AUTH", True))


def user_role(user) -> str:
    if not user or not user.is_authenticated:
        return ""
    if user.is_superuser:
        return "admin"
    try:
        return (user.profile.role or "lawyer").strip() or "lawyer"
    except Exception:
        return "lawyer"


def role_required(*roles: str):
    """Require login + one of the given roles (admin always allowed)."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not auth_required():
                return view_func(request, *args, **kwargs)
            if not request.user.is_authenticated:
                if request.path.startswith("/api/") or request.headers.get("Accept") == "application/json":
                    return JsonResponse({"error": "authentication required"}, status=401)
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")
            role = user_role(request.user)
            if role == "admin" or role in roles:
                return view_func(request, *args, **kwargs)
            if request.path.startswith("/api/"):
                return JsonResponse({"error": "forbidden"}, status=403)
            raise PermissionDenied("Insufficient role")

        return _wrapped

    return decorator


def login_required_if_auth(view_func):
    """login_required only when REQUIRE_AUTH is on."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not auth_required():
            return view_func(request, *args, **kwargs)
        return login_required(view_func)(request, *args, **kwargs)

    return _wrapped


class LoginRequiredMixin:
    """CBV mixin — skip when REQUIRE_AUTH is False (tests)."""

    def dispatch(self, request, *args, **kwargs):
        if not auth_required():
            return super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")
        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin:
    """CBV mixin — set `required_roles = ('lawyer',)` or `('admin',)`."""

    required_roles: tuple[str, ...] = ("lawyer",)

    def dispatch(self, request, *args, **kwargs):
        if not auth_required():
            return super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            if request.path.startswith("/api/"):
                return JsonResponse({"error": "authentication required"}, status=401)
            return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")
        role = user_role(request.user)
        if role == "admin" or role in self.required_roles:
            return super().dispatch(request, *args, **kwargs)
        if request.path.startswith("/api/"):
            return JsonResponse({"error": "forbidden"}, status=403)
        raise PermissionDenied("Insufficient role")
