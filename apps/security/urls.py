from django.urls import path

from apps.security import views

app_name = "security"

urlpatterns = [
    path("security/<uuid:pk>/", views.SecurityAlertView.as_view(), name="alert"),
    path(
        "security/<uuid:pk>/override/",
        views.SecurityOverrideView.as_view(),
        name="override",
    ),
]
