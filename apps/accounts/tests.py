"""Auth / CSRF / admin reset smoke tests."""

from __future__ import annotations

import json

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from apps.accounts.models import UserProfile, ensure_profile


@override_settings(REQUIRE_AUTH=True)
class AuthHardeningTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.lawyer = User.objects.create_user("lawyer_t", password="x")
        p = ensure_profile(self.lawyer)
        p.role = UserProfile.Role.LAWYER
        p.onboarding_complete = True
        p.save()
        self.admin = User.objects.create_user("admin_t", password="x")
        ap = ensure_profile(self.admin)
        ap.role = UserProfile.Role.ADMIN
        ap.onboarding_complete = True
        ap.save()

    def test_unauth_api_401(self):
        r = self.client.post(
            "/api/admin/reset-decisions/",
            data=json.dumps({"confirm": "RESET"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 401)

    def test_csrf_missing_post_403(self):
        self.client.login(username="admin_t", password="x")
        r = self.client.post(
            "/api/admin/reset-decisions/",
            data=json.dumps({"confirm": "RESET"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)

    def test_admin_reset_with_csrf(self):
        self.client.login(username="admin_t", password="x")
        self.client.get("/login/")  # ensure csrf cookie
        token = self.client.cookies.get("csrftoken").value
        r = self.client.post(
            "/api/admin/reset-decisions/",
            data=json.dumps({"confirm": "RESET"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

    def test_lawyer_forbidden_admin_reset(self):
        self.client.login(username="lawyer_t", password="x")
        self.client.get("/login/")
        token = self.client.cookies.get("csrftoken").value
        r = self.client.post(
            "/api/admin/reset-decisions/",
            data=json.dumps({"confirm": "RESET"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(r.status_code, 403)

    def test_security_headers(self):
        r = self.client.get("/trust/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertTrue(r.get("Referrer-Policy"))

    def test_media_allows_framing(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from apps.accounts.security_headers import ExtraSecurityHeadersMiddleware

        def get_response(request):
            resp = HttpResponse(b"%PDF", content_type="application/pdf")
            resp["X-Frame-Options"] = "SAMEORIGIN"
            return resp

        mw = ExtraSecurityHeadersMiddleware(get_response)
        req = RequestFactory().get("/media/contracts/demo.pdf")
        r = mw(req)
        self.assertIsNone(r.get("X-Frame-Options"))
        self.assertIn("frame-ancestors 'self'", r.get("Content-Security-Policy") or "")


class ReactDraftTests(TestCase):
    def test_fake_react_trace(self):
        from apps.drafting.agent import react_draft

        result = react_draft(
            finding_payload={
                "playbook_rule_id": "r1",
                "clause_excerpt": "California law",
                "status": "needs_human",
            },
            playbook_rule={
                "id": "r1",
                "preferred": "England and Wales",
                "fallback_text": "E&W",
            },
        )
        self.assertTrue(result.draft_text)
        trace = result.provenance.get("react_trace") or []
        self.assertGreaterEqual(len(trace), 3)
        self.assertLessEqual(len(trace), 6)
