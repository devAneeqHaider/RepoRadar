"""Database models for analyzed repositories and their analysis jobs."""
import uuid

from django.db import models


class Repository(models.Model):
    """A public GitHub repository that RepoRadar has analyzed (or will analyze)."""

    url = models.URLField(unique=True, max_length=500)
    owner = models.CharField(max_length=200)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    language = models.CharField(max_length=100, blank=True, default="")
    stars = models.IntegerField(default=0)
    default_branch = models.CharField(max_length=100, default="main")
    analyzed_at = models.DateTimeField(null=True, blank=True)

    # Analysis artifacts, produced by analyzer.services + ai_engine.services.
    stats = models.JSONField(default=dict)
    graph_data = models.JSONField(default=dict)
    smells = models.JSONField(default=list)
    guide_markdown = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.owner}/{self.name}"


class AnalysisJob(models.Model):
    """Tracks one background analysis run for a repository."""

    STATUS_PENDING = "pending"
    STATUS_DOWNLOADING = "downloading"
    STATUS_PARSING = "parsing"
    STATUS_ANALYZING = "analyzing"
    STATUS_AI = "ai"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_DOWNLOADING, "Downloading"),
        (STATUS_PARSING, "Parsing"),
        (STATUS_ANALYZING, "Analyzing"),
        (STATUS_AI, "AI enrichment"),
        (STATUS_DONE, "Done"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository = models.ForeignKey(
        Repository,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    progress = models.IntegerField(default=0)
    message = models.CharField(max_length=500, blank=True, default="")
    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Job {self.id} [{self.status}]"
