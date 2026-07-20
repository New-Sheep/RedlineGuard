from django.urls import path

from apps.decisions import views

app_name = "decisions"

urlpatterns = [
    path("history/", views.HistoryView.as_view(), name="history"),
    path("audit/", views.AuditLogView.as_view(), name="audit"),
    path(
        "decisions/<uuid:pk>/undo/",
        views.DecisionUndoView.as_view(),
        name="undo",
    ),
    path(
        "decisions/<uuid:pk>/redo/",
        views.DecisionRedoView.as_view(),
        name="redo",
    ),
    # APIs
    path("api/contracts/", views.ApiContractsListView.as_view(), name="api_contracts"),
    path(
        "api/decisions/<uuid:pk>/",
        views.ApiDecisionDetailView.as_view(),
        name="api_decision",
    ),
    path("api/overrides/", views.ApiOverridesView.as_view(), name="api_overrides"),
    path(
        "api/overrides/<str:rule_id>/",
        views.ApiOverridesView.as_view(),
        name="api_override_delete",
    ),
    path(
        "api/playbooks/activate-restore/",
        views.ApiPlaybookRestoreView.as_view(),
        name="api_playbook_restore",
    ),
    path("api/playbook/", views.ApiPlaybookActiveView.as_view(), name="api_playbook"),
    path("api/findings/", views.ApiFindingsListView.as_view(), name="api_findings"),
    path(
        "api/security-events/",
        views.ApiSecurityEventsView.as_view(),
        name="api_security_events",
    ),
    path("api/audit/", views.ApiAuditListView.as_view(), name="api_audit"),
]
