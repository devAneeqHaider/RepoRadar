"""RepoRadar API v1 URL map — mounted under /api/ by config.urls."""
from django.urls import path

from api import views

urlpatterns = [
    path("analyze/", views.AnalyzeView.as_view(), name="analyze"),
    path("jobs/<uuid:job_id>/", views.JobDetailView.as_view(), name="job-detail"),
    path("repos/", views.RepositoryListView.as_view(), name="repo-list"),
    path("repos/<int:pk>/", views.RepositoryDetailView.as_view(), name="repo-detail"),
    path(
        "repos/<int:pk>/graph/",
        views.RepositoryGraphView.as_view(),
        name="repo-graph",
    ),
    path(
        "repos/<int:pk>/smells/",
        views.RepositorySmellsView.as_view(),
        name="repo-smells",
    ),
    path(
        "repos/<int:pk>/guide/",
        views.RepositoryGuideView.as_view(),
        name="repo-guide",
    ),
]
