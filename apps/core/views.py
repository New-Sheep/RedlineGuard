"""Core pages — help / tutorial / trust."""

from __future__ import annotations

from django.shortcuts import render
from django.views import View


class HelpView(View):
    template_name = "core/help.html"

    def get(self, request):
        return render(request, self.template_name)


class TrustView(View):
    """Public explainability pack — open without login for demos."""

    template_name = "core/trust.html"

    def get(self, request):
        return render(request, self.template_name)
