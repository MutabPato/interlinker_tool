"""URL configuration for the interlinker app.

This module defines the URL patterns for the app's views. It also
specifies the ``app_name`` to allow namespacing from the project URL
configuration.
"""

from django.urls import path

from . import views


app_name = 'interlinker'

urlpatterns = [
    path('', views.home, name='home'),
    path('sitemap/upload/', views.upload_sitemap, name='sitemap_upload'),
    path('sitemap/links/', views.sitemap_links, name='sitemap_links'),
    path('interlink/', views.interlink, name='interlink'),
]