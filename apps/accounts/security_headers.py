"""Extra security headers not covered by Django defaults."""

from __future__ import annotations

from django.conf import settings


class ExtraSecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Referrer-Policy
        if not response.get("Referrer-Policy"):
            response["Referrer-Policy"] = getattr(
                settings, "SECURE_REFERRER_POLICY", "same-origin"
            )
        # Media (contract PDFs) must be frameable by our own Review iframe
        media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"
        if request.path.startswith(media_url):
            if "X-Frame-Options" in response:
                del response["X-Frame-Options"]
            response["Content-Security-Policy"] = "frame-ancestors 'self'"
        else:
            csp = getattr(settings, "CONTENT_SECURITY_POLICY_REPORT_ONLY", "")
            if csp and not response.get("Content-Security-Policy-Report-Only"):
                response["Content-Security-Policy-Report-Only"] = csp
        # Never leak stack traces on JSON 500s from our APIs
        if (
            request.path.startswith("/api/")
            and response.status_code >= 500
            and "application/json" not in (response.get("Content-Type") or "")
        ):
            from django.http import JsonResponse

            return JsonResponse({"error": "internal server error"}, status=500)
        return response
