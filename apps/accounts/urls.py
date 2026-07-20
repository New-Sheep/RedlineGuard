from django.urls import path

from apps.accounts import views
from apps.accounts import onboarding
from apps.accounts import admin_ops

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("onboarding/", onboarding.OnboardingView.as_view(), name="onboarding"),
    path("lab/", admin_ops.LabResetView.as_view(), name="lab_reset"),
    path(
        "contracts/<uuid:pk>/delete/",
        admin_ops.ContractDeleteFormView.as_view(),
        name="contract_delete",
    ),
    path(
        "api/contracts/<uuid:pk>/",
        admin_ops.ApiContractDeleteView.as_view(),
        name="api_contract_delete",
    ),
    path(
        "api/admin/reset-decisions/",
        admin_ops.ApiResetDecisionsView.as_view(),
        name="api_reset_decisions",
    ),
    path(
        "api/admin/reset-contracts/",
        admin_ops.ApiResetContractsView.as_view(),
        name="api_reset_contracts",
    ),
    path(
        "api/admin/reset-overrides/",
        admin_ops.ApiResetOverridesView.as_view(),
        name="api_reset_overrides",
    ),
    path(
        "api/admin/reset-onboarding/",
        admin_ops.ApiResetOnboardingView.as_view(),
        name="api_reset_onboarding",
    ),
]
