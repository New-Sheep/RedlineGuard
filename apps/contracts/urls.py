from django.urls import path

from apps.contracts import views

app_name = "contracts"

urlpatterns = [
    path("", views.UploadView.as_view(), name="upload"),
    path("contracts/<uuid:pk>/", views.ContractDetailView.as_view(), name="detail"),
    path(
        "contracts/<uuid:pk>/processing/",
        views.ProcessingView.as_view(),
        name="processing",
    ),
    path(
        "contracts/<uuid:pk>/status.json",
        views.ContractStatusJsonView.as_view(),
        name="status_json",
    ),
    path("contracts/<uuid:pk>/review/", views.ReviewView.as_view(), name="review"),
]
