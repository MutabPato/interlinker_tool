"""Django views for the interlinker app.

These views handle rendering pages for uploading sitemaps, listing
extracted links and domains, and interlinking user-provided content.
Each view uses the forms and services provided by the application to
perform its work.
"""

from __future__ import annotations

import gzip
from typing import List, Tuple

from django.contrib import messages
from django.db import models, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .forms import InterlinkForm, SitemapUploadForm
from .models import Domain, Link
from .services import (
    build_link_map,
    fetch_sitemap_text,
    interlink_html,
    normalize_slug_from_url,
    parse_sitemap,
)


def home(request: HttpRequest) -> HttpResponse:
    """Render the home page which offers navigation to app features."""
    return render(request, 'interlinker/home.html')


@transaction.atomic
def upload_sitemap(request: HttpRequest) -> HttpResponse:
    """Handle uploading or fetching a sitemap and storing its links.

    The view accepts either a direct sitemap URL, an uploaded file or a
    base URL. When a base URL is provided without an explicit sitemap
    location it will attempt to fetch ``<base>/sitemap.xml``. All
    discovered links are normalised and stored in the database under the
    appropriate ``Domain``. If an existing domain is found it will
    update or create links as needed.
    """
    if request.method == 'POST':
        form = SitemapUploadForm(request.POST, request.FILES)
        if form.is_valid():
            base_url = form.cleaned_data.get('base_url')
            sitemap_url = form.cleaned_data.get('sitemap_url')
            file_obj = form.cleaned_data.get('file')
            xml_text: str | None = None
            # Priority: file upload > sitemap URL > base URL default
            if file_obj:
                # Read the uploaded file; support binary files such as .gz
                data = file_obj.read()
                # Attempt to decompress gzipped file
                if getattr(file_obj, 'name', '').lower().endswith('.gz'):
                    try:
                        data = gzip.decompress(data)
                    except OSError:
                        pass
                try:
                    xml_text = data.decode('utf-8')
                except UnicodeDecodeError:
                    xml_text = data.decode('latin-1', errors='ignore')
            else:
                # Determine the URL to fetch
                url_to_fetch = None
                if sitemap_url:
                    url_to_fetch = sitemap_url
                elif base_url:
                    url_to_fetch = base_url.rstrip('/') + '/sitemap.xml'
                if url_to_fetch:
                    xml_text = fetch_sitemap_text(url_to_fetch)
            if xml_text:
                urls = parse_sitemap(xml_text)
                if not urls:
                    messages.warning(request, 'No URLs were found in the provided sitemap.')
                # If base_url not provided but sitemap_url is, infer the base domain
                from urllib.parse import urlparse
                if not base_url:
                    if sitemap_url:
                        pr = urlparse(sitemap_url)
                        base_url = f'{pr.scheme}://{pr.netloc}'
                # Ensure we have a domain object
                if not base_url:
                    messages.error(request, 'Base URL could not be determined.')
                    return redirect('interlinker:sitemap_upload')
                parsed_base = urlparse(base_url)
                hostname = parsed_base.hostname or parsed_base.netloc or base_url
                domain, _ = Domain.objects.get_or_create(
                    base_url=base_url,
                    defaults={'hostname': hostname},
                )
                count = 0
                for u in urls:
                    # Only store links from the same hostname
                    pr = urlparse(u)
                    if pr.hostname and pr.hostname != hostname:
                        continue
                    raw_slug, norm_slug = normalize_slug_from_url(u)
                    # Create or update the link
                    Link.objects.update_or_create(
                        domain=domain,
                        url=u,
                        defaults={
                            'slug': norm_slug,
                            'raw_slug': raw_slug,
                        },
                    )
                    count += 1
                messages.success(request, f'Imported {count} links for {domain.base_url}.')
                return redirect('interlinker:sitemap_links')
            else:
                messages.error(request, 'Unable to fetch or parse the sitemap. Please check the URL or file.')
    else:
        form = SitemapUploadForm()
    return render(request, 'interlinker/sitemap_upload.html', {'form': form})


def sitemap_links(request: HttpRequest) -> HttpResponse:
    """List stored links filtered by domain and search query."""
    domain_id = request.GET.get('domain')
    query = request.GET.get('q', '')
    domains = Domain.objects.all()
    links = Link.objects.select_related('domain').all()
    if domain_id:
        try:
            domain_id_int = int(domain_id)
            links = links.filter(domain_id=domain_id_int)
        except (ValueError, TypeError):
            pass
    if query:
        # search slug and raw_slug and title for query
        links = links.filter(
            models.Q(slug__icontains=query) |
            models.Q(raw_slug__icontains=query) |
            models.Q(title__icontains=query)
        )
    links = links.order_by('domain', 'slug')
    return render(
        request,
        'interlinker/sitemap_links.html',
        {
            'links': links,
            'domains': domains,
            'selected_domain': domain_id,
            'query': query,
        },
    )


def interlink(request: HttpRequest) -> HttpResponse:
    """Handle displaying the interlink form and processing the content."""
    if request.method == 'POST':
        form = InterlinkForm(request.POST)
        if form.is_valid():
            domain: Domain = form.cleaned_data['domain']
            content: str = form.cleaned_data['content']
            max_links: int = form.cleaned_data['max_links']
            is_html: bool = form.cleaned_data['is_html_input']
            slug_map = build_link_map(domain)
            if not slug_map:
                messages.warning(request, 'There are no links stored for this domain.')
                return render(request, 'interlinker/interlink_form.html', {'form': form})
            # If the content is not HTML, wrap paragraphs in <p> tags
            if not is_html:
                paragraphs = [p.strip() for p in content.splitlines() if p.strip()]
                html_input = ''.join(f'<p>{p}</p>' for p in paragraphs)
            else:
                html_input = content
            linked_html = interlink_html(html_input, slug_map, max_links=max_links)
            # Build a list of inserted links for summary
            inserted: List[Tuple[str, str]] = []
            for slug, url in slug_map.items():
                if f'href="{url}"' in linked_html:
                    inserted.append((slug, url))
            return render(
                request,
                'interlinker/interlink_result.html',
                {
                    'linked_html': linked_html,
                    'inserted': inserted,
                },
            )
    else:
        form = InterlinkForm()
    return render(request, 'interlinker/interlink_form.html', {'form': form})


@require_GET
def robots_txt(request: HttpRequest) -> HttpResponse:
    """Serve a robots.txt that advertises the app sitemap."""

    sitemap_url = request.build_absolute_uri(reverse('interlinker:sitemap_xml'))
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {sitemap_url}\n"
    )
    return HttpResponse(content, content_type='text/plain')


@require_GET
def sitemap_xml(request: HttpRequest) -> HttpResponse:
    """Expose a minimal sitemap for the application itself."""

    base_url = f"{request.scheme}://{request.get_host()}"
    static_paths = [
        reverse('interlinker:home'),
        reverse('interlinker:sitemap_upload'),
        reverse('interlinker:sitemap_links'),
        reverse('interlinker:interlink'),
    ]
    lines = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">",
    ]
    for path in static_paths:
        lines.extend([
            "  <url>",
            f"    <loc>{base_url}{path}</loc>",
            "    <changefreq>weekly</changefreq>",
            "    <priority>0.6</priority>",
            "  </url>",
        ])
    lines.append("</urlset>")
    return HttpResponse('\n'.join(lines), content_type='application/xml')
