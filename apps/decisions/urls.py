from django.urls import path

from apps.decisions import views

app_name = "decisions"

urlpatterns = [
    path("history/", views.HistoryView.as_view(), name="history"),
]
