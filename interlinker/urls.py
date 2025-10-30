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
    path('privacy/', views.privacy, name='privacy'),
    path('sitemap/upload/', views.upload_sitemap, name='sitemap_upload'),
    path('sitemap/links/', views.sitemap_links, name='sitemap_links'),
    path('account/signup/', views.signup, name='signup'),
    path('account/history/', views.interlink_history, name='history'),
    path('interlink/', views.interlink, name='interlink'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
]
