"""Forms for the interlinker app.

The forms define user-facing inputs for uploading sitemaps and interlinking
blog/review content. Validation rules ensure sensible defaults and required
fields.
"""

from __future__ import annotations

from django import forms

from .models import Domain


class SitemapUploadForm(forms.Form):
    """Form used to ingest a sitemap from either a URL or an uploaded file."""

    base_url = forms.URLField(
        required=False,
        label='Base URL',
        help_text='The root URL of the site (e.g. https://example.com).'
    )
    sitemap_url = forms.URLField(
        required=False,
        label='Sitemap URL',
        help_text='Explicit URL of the sitemap (e.g. https://example.com/sitemap.xml).'
    )
    file = forms.FileField(
        required=False,
        label='Upload sitemap file',
        help_text='Upload an XML or XML.GZ sitemap file.',
    )

    def clean(self) -> dict[str, str]:  # type: ignore[override]
        cleaned_data = super().clean()
        base_url = cleaned_data.get('base_url')
        sitemap_url = cleaned_data.get('sitemap_url')
        file_obj = cleaned_data.get('file')
        if not (sitemap_url or file_obj or base_url):
            raise forms.ValidationError(
                'You must provide either a sitemap URL, upload a file, or a base URL.'
            )
        return cleaned_data


class InterlinkForm(forms.Form):
    """Form used for interlinking a block of text with stored links."""

    domain = forms.ModelChoiceField(
        queryset=Domain.objects.all(),
        label='Domain',
        help_text='Choose which site to use for matching links.'
    )
    content = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 15}),
        label='Content',
        help_text='Paste the review or blog post content here.'
    )
    max_links = forms.IntegerField(
        min_value=1,
        max_value=25,
        initial=10,
        label='Maximum links',
        help_text='The maximum number of links to insert (default 10).'
    )
    is_html_input = forms.BooleanField(
        required=False,
        label='Content is HTML',
        help_text='Check if your content already contains HTML markup.'
    )