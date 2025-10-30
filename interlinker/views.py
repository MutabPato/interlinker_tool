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
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.db import models, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .forms import InterlinkForm, LoginForm, SignUpForm, SitemapUploadForm
from .models import Domain, InterlinkGeneration, Link
from .services import (
    build_link_map,
    fetch_sitemap_text,
    interlink_html,
    normalize_slug_from_url,
    parse_sitemap,
    strip_existing_links_from_html,
)


def home(request: HttpRequest) -> HttpResponse:
    """Render the home page which offers navigation to app features."""
    return render(request, 'interlinker/home.html')


def privacy(request: HttpRequest) -> HttpResponse:
    """Display the privacy policy for Interlinker."""

    return render(request, 'interlinker/privacy.html')


class InterlinkLoginView(DjangoLoginView):
    """Custom login view that uses the app styling and redirects to interlink."""

    form_class = LoginForm
    template_name = 'registration/login.html'

    def get_success_url(self) -> str:
        return self.get_redirect_url() or reverse('interlinker:interlink')


def signup(request: HttpRequest) -> HttpResponse:
    """Allow new users to create an account and begin interlinking."""

    if request.user.is_authenticated:
        messages.info(request, 'You already have an account and are signed in.')
        return redirect('interlinker:interlink')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created — welcome aboard!')
            return redirect('interlinker:interlink')
    else:
        form = SignUpForm()

    return render(request, 'interlinker/account_register.html', {'form': form})


@login_required
def interlink_history(request: HttpRequest) -> HttpResponse:
    """List previous interlink generations for the signed-in user."""

    generations = (
        InterlinkGeneration.objects
        .filter(user=request.user)
        .select_related('domain')
        .order_by('-created_at')
    )

    return render(
        request,
        'interlinker/history.html',
        {
            'generations': generations,
        },
    )


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


@login_required
def interlink(request: HttpRequest) -> HttpResponse:
    """Handle displaying the interlink form and processing the content."""
    if request.method == 'POST':
        form = InterlinkForm(request.POST)
        if form.is_valid():
            domain: Domain = form.cleaned_data['domain']
            content: str = form.cleaned_data['content']
            max_links: int = form.cleaned_data['max_links']
            is_html: bool = form.cleaned_data['is_html_input']
            strip_links: bool = form.cleaned_data['strip_existing_links']
            slug_map = build_link_map(domain)
            priority_pairs: List[Tuple[str, str]] = form.cleaned_data['priority_pairs']
            if not slug_map and not priority_pairs:
                messages.warning(request, 'There are no links stored for this domain yet.')
                return render(request, 'interlinker/interlink_form.html', {'form': form})
            # If the content is not HTML, wrap paragraphs in <p> tags
            if not is_html:
                paragraphs = [p.strip() for p in content.splitlines() if p.strip()]
                html_input = ''.join(f'<p>{p}</p>' for p in paragraphs)
            else:
                html_input = content
            if strip_links:
                html_input = strip_existing_links_from_html(html_input)
            linked_html, inserted = interlink_html(
                html_input,
                slug_map,
                max_links=max_links,
                priority_pairs=priority_pairs,
            )

            def _normalise(term: str) -> str:
                return ' '.join(term.lower().split())

            total_inserted = len(inserted)
            priority_inserted = sum(1 for item in inserted if item.priority)
            auto_inserted = total_inserted - priority_inserted

            inserted_records = [
                {
                    'term': item.term,
                    'url': item.url,
                    'priority': item.priority,
                    'context': item.context,
                }
                for item in inserted
            ]
            priority_pairs_data = [
                {'term': term, 'url': url}
                for term, url in priority_pairs
            ]
            excerpt_source = content if not is_html else html_input
            excerpt = (excerpt_source or '').strip()
            if len(excerpt) > 1000:
                excerpt = f"{excerpt[:1000].rstrip()}…"

            InterlinkGeneration.objects.create(
                user=request.user,
                domain=domain,
                source_excerpt=excerpt,
                linked_html=linked_html,
                inserted_total=total_inserted,
                inserted_priority=priority_inserted,
                inserted_auto=auto_inserted,
                max_links=max_links,
                source_is_html=is_html,
                priority_pairs=priority_pairs_data,
                inserted_records=inserted_records,
            )

            priority_missing = [
                pair['term']
                for pair in priority_pairs_data
                if _normalise(pair['term']) not in {_normalise(item.term) for item in inserted if item.priority}
            ]
            return render(
                request,
                'interlinker/interlink_result.html',
                {
                    'linked_html': linked_html,
                    'inserted': inserted,
                    'priority_missing': priority_missing,
                    'priority_inserted': priority_inserted,
                    'auto_inserted': auto_inserted,
                    'total_inserted': total_inserted,
                    'max_links': max_links,
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
