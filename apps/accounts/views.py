from __future__ import annotations

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.accounts.models import ensure_profile


def _login_rate_ok(request) -> bool:
    cap = int(getattr(settings, "MAX_LOGIN_ATTEMPTS_PER_HOUR", 20))
    n = int(request.session.get("login_attempts") or 0)
    return n < cap


def _bump_login_attempt(request) -> None:
    request.session["login_attempts"] = int(request.session.get("login_attempts") or 0) + 1


@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginView(View):
    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("contracts:list")
        return render(request, self.template_name, {"form": AuthenticationForm()})

    def post(self, request):
        if not _login_rate_ok(request):
            form = AuthenticationForm(request)
            form.add_error(None, "Too many login attempts. Try again later.")
            return render(request, self.template_name, {"form": form}, status=429)
        form = AuthenticationForm(request, data=request.POST)
        if not form.is_valid():
            _bump_login_attempt(request)
            return render(request, self.template_name, {"form": form}, status=400)
        user = form.get_user()
        login(request, user)
        request.session["login_attempts"] = 0
        ensure_profile(user)
        next_url = request.GET.get("next") or request.POST.get("next") or ""
        profile = ensure_profile(user)
        if not profile.onboarding_complete and not next_url.startswith("/onboarding"):
            return redirect("accounts:onboarding")
        if next_url:
            return redirect(next_url)
        return redirect("contracts:list")


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("accounts:login")

    def get(self, request):
        logout(request)
        return redirect("accounts:login")
