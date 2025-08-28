from django.contrib import admin

from .models import Domain, Link


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('base_url', 'hostname', 'created_at')
    search_fields = ('base_url', 'hostname')


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ('url', 'domain', 'slug', 'raw_slug', 'title', 'created_at')
    list_filter = ('domain',)
    search_fields = ('url', 'slug', 'raw_slug', 'title')