from django.urls import path

from apps.learning import views

app_name = "learning"

urlpatterns = [
    path("memory/", views.MemoryPageView.as_view(), name="memory"),
    path(
        "memory/<str:precedent_id>/unlearn/",
        views.MemoryUnlearnView.as_view(),
        name="unlearn",
    ),
    path(
        "memory/revoke-override/",
        views.MemoryRevokeOverrideView.as_view(),
        name="revoke_override",
    ),
    path("api/memory/", views.MemoryListApiView.as_view(), name="api_list"),
    path("api/memory/search/", views.MemorySearchApiView.as_view(), name="api_search"),
    path(
        "api/memory/<str:precedent_id>/",
        views.MemoryDeleteApiView.as_view(),
        name="api_delete",
    ),
]
