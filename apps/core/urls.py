from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("help/", views.HelpView.as_view(), name="help"),
    path("trust/", views.TrustView.as_view(), name="trust"),
]
