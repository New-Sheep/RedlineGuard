from __future__ import annotations

from django.shortcuts import render
from django.views import View

from apps.decisions.models import Decision


class HistoryView(View):
    template_name = "decisions/history.html"

    def get(self, request):
        decisions = Decision.objects.select_related(
            "finding", "contract"
        ).order_by("-created_at")[:100]
        return render(request, self.template_name, {"decisions": decisions})
