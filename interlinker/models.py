"""Database models for the interlinker app.

The app stores sites (domains) and individual links extracted from their
sitemaps. Each link has a raw slug extracted from its URL and a normalized
slug used for matching keywords in reviews or blog posts.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Domain(models.Model):
    """Represents a website/domain whose sitemap has been ingested."""

    base_url = models.URLField(unique=True)
    hostname = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - convenience display
        return self.base_url


class Link(models.Model):
    """Represents an internal link extracted from a domain's sitemap."""

    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='links')
    url = models.URLField()
    slug = models.CharField(max_length=255, db_index=True)
    raw_slug = models.CharField(max_length=255)
    title = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('domain', 'url')

    def __str__(self) -> str:  # pragma: no cover - convenience display
        return self.url


class InterlinkGeneration(models.Model):
    """Stores a single interlink generation run for a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='interlink_generations',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interlink_generations',
    )
    source_excerpt = models.TextField()
    linked_html = models.TextField()
    inserted_total = models.PositiveSmallIntegerField(default=0)
    inserted_priority = models.PositiveSmallIntegerField(default=0)
    inserted_auto = models.PositiveSmallIntegerField(default=0)
    max_links = models.PositiveSmallIntegerField(default=10)
    source_is_html = models.BooleanField(default=False)
    priority_pairs = models.JSONField(default=list, blank=True)
    inserted_records = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:  # pragma: no cover - convenience display
        domain = self.domain.hostname if self.domain else 'unknown domain'
        return f"{self.user} · {domain} · {self.created_at:%Y-%m-%d %H:%M}"
