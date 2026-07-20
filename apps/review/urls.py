from django.urls import path

from apps.review import views

app_name = "review"

urlpatterns = [
    path("playbook/", views.ActivePlaybookView.as_view(), name="playbook_active"),
    path("playbook/import/", views.PlaybookImportView.as_view(), name="playbook_import"),
    path(
        "playbook/starter/",
        views.PlaybookStarterView.as_view(),
        name="playbook_starter",
    ),
    path(
        "playbook/imports/<uuid:pk>/processing/",
        views.PlaybookImportProcessingView.as_view(),
        name="playbook_import_processing",
    ),
    path(
        "playbook/imports/<uuid:pk>/status.json",
        views.PlaybookImportStatusJsonView.as_view(),
        name="playbook_import_status",
    ),
    path(
        "playbook/imports/<uuid:pk>/",
        views.PlaybookImportDetailView.as_view(),
        name="playbook_import_detail",
    ),
    path(
        "contracts/<uuid:contract_id>/rewrite/<uuid:finding_id>/",
        views.RewriteView.as_view(),
        name="rewrite",
    ),
    path(
        "contracts/<uuid:pk>/brief.json",
        views.DecisionBriefJsonView.as_view(),
        name="decision_brief",
    ),
    path(
        "contracts/<uuid:contract_id>/findings/<uuid:finding_id>/ask/",
        views.FindingAskView.as_view(),
        name="finding_ask",
    ),
    path(
        "playbook/gaps/",
        views.GapSuggestView.as_view(),
        name="gap_suggest",
    ),
    path(
        "contracts/<uuid:contract_id>/missed-clause/",
        views.MissedClauseCreateView.as_view(),
        name="missed_clause_create",
    ),
    path(
        "missed-clauses/<uuid:pk>/",
        views.MissedClauseDetailView.as_view(),
        name="missed_clause_detail",
    ),
]
