"""DRF serializers for the RepoRadar API contract (v1)."""
from rest_framework import serializers

from repositories.models import AnalysisJob, Repository


class RepositoryListSerializer(serializers.ModelSerializer):
    """Exactly the contract list fields."""

    class Meta:
        model = Repository
        fields = ["id", "owner", "name", "url", "language", "stars", "analyzed_at"]


class RepositoryDetailSerializer(serializers.ModelSerializer):
    """Full repo detail: list fields + description, stats, guide presence."""

    has_guide = serializers.SerializerMethodField()

    class Meta:
        model = Repository
        fields = [
            "id",
            "owner",
            "name",
            "url",
            "description",
            "language",
            "stars",
            "default_branch",
            "analyzed_at",
            "stats",
            "has_guide",
            "created_at",
            "updated_at",
        ]

    def get_has_guide(self, obj: Repository) -> bool:
        return bool(obj.guide_markdown)


class AnalysisJobSerializer(serializers.ModelSerializer):
    """Job status payload; ``id`` is exposed as ``job_id`` per contract."""

    job_id = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = AnalysisJob
        fields = [
            "job_id",
            "status",
            "progress",
            "message",
            "error",
            "repository_id",
        ]
