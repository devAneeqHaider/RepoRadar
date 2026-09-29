"""Thin API views — all business logic lives in analyzer/ai_engine services."""
import logging
import re

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from analyzer.tasks import run_analysis
from api.serializers import (
    AnalysisJobSerializer,
    RepositoryDetailSerializer,
    RepositoryListSerializer,
)
from api.report_pdf import build_repository_report
from repositories.models import AnalysisJob, Repository

logger = logging.getLogger(__name__)

REPO_URL_RE = re.compile(r"^https://github\.com/([^/\s]+)/([^/\s]+)/?$")


def _normalize_repo_url(url: str) -> tuple[str, str, str]:
    """Validate a GitHub URL -> (canonical_url, owner, name). Raises ValueError."""
    match = REPO_URL_RE.match((url or "").strip())
    if not match:
        raise ValueError(
            "repo_url must look like https://github.com/<owner>/<repo>"
        )
    owner, name = match.group(1), match.group(2)
    if name.endswith(".git"):
        name = name[: -len(".git")]
    return f"https://github.com/{owner}/{name}", owner, name


class AnalyzeView(APIView):
    """POST /api/analyze/ -> 202 {"job_id": "<uuid>"}."""

    def post(self, request):
        try:
            url, owner, name = _normalize_repo_url(request.data.get("repo_url"))
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        repository, _ = Repository.objects.get_or_create(
            url=url, defaults={"owner": owner, "name": name}
        )
        job = AnalysisJob.objects.create(repository=repository)
        try:
            run_analysis.delay(str(job.id))
        except Exception:  # noqa: BLE001 - broker down; job stays pending
            logger.exception(
                "Celery broker unreachable; job %s queued in DB only", job.id
            )
        return Response({"job_id": str(job.id)}, status=status.HTTP_202_ACCEPTED)


class JobDetailView(generics.RetrieveAPIView):
    """GET /api/jobs/<uuid>/ — 404 on unknown uuid."""

    queryset = AnalysisJob.objects.select_related("repository").all()
    serializer_class = AnalysisJobSerializer
    lookup_field = "id"
    lookup_url_kwarg = "job_id"


class RepositoryListView(generics.ListAPIView):
    """GET /api/repos/."""

    queryset = Repository.objects.all().order_by("-analyzed_at", "-created_at")
    serializer_class = RepositoryListSerializer


class RepositoryDetailView(generics.RetrieveAPIView):
    """GET /api/repos/<id>/ — full detail + stats."""

    queryset = Repository.objects.all()
    serializer_class = RepositoryDetailSerializer


class RepositoryGraphView(APIView):
    """GET /api/repos/<id>/graph/."""

    def get(self, request, pk):
        repository = get_object_or_404(Repository, pk=pk)
        return Response(repository.graph_data or {"nodes": [], "edges": []})


class RepositorySmellsView(APIView):
    """GET /api/repos/<id>/smells/."""

    def get(self, request, pk):
        repository = get_object_or_404(Repository, pk=pk)
        return Response(repository.smells or [])


class RepositoryGuideView(APIView):
    """GET /api/repos/<id>/guide/."""

    def get(self, request, pk):
        repository = get_object_or_404(Repository, pk=pk)
        return Response({"markdown": repository.guide_markdown or ""})


class RepositoryReportView(APIView):
    """GET /api/repos/<id>/report/ -> downloadable PDF analysis report."""

    def get(self, request, pk):
        repository = get_object_or_404(Repository, pk=pk)
        pdf = build_repository_report(repository)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", repository.name).strip("-.") or "repository"
        safe_owner = re.sub(r"[^A-Za-z0-9._-]+", "-", repository.owner).strip("-.") or "owner"
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{safe_owner}-{safe_name}-report.pdf"'
        )
        return response
