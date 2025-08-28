"""Database models for the interlinker app.

The app stores sites (domains) and individual links extracted from their
sitemaps. Each link has a raw slug extracted from its URL and a normalized
slug used for matching keywords in reviews or blog posts.
"""

from __future__ import annotations

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