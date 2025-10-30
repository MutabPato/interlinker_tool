"""Pytest configuration shared across test modules."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "interlinker_tool.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
os.environ.setdefault("DJANGO_DEBUG", "true")
