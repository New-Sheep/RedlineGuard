from __future__ import annotations

from django.shortcuts import get_object_or_404, render
from django.views import View

from apps.contracts.models import Contract
from apps.security.models import SecurityEvent


class SecurityAlertView(View):
    template_name = "security/alert.html"

    def get(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        event = (
            SecurityEvent.objects.filter(contract=contract, halt=True)
            .order_by("-created_at")
            .first()
        )
        return render(
            request,
            self.template_name,
            {"contract": contract, "event": event},
        )
