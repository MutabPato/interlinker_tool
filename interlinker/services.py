"""Service functions for ingesting sitemaps and interlinking text.

These functions encapsulate the core logic of the application so they
can be easily unit tested and reused from the views. They handle
fetching and parsing sitemap XML, normalising slugs from URLs, building
a slug→URL map from stored links, and inserting anchor tags into HTML
content based on keywords.
"""

from __future__ import annotations

import gzip
import re
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple
from xml.etree import ElementTree

from bs4 import BeautifulSoup, NavigableString  # type: ignore

from .models import Domain

# Tags inside which links should never be inserted
SKIP_TAGS: set[str] = {"a", "code", "pre", "h1", "h2", "h3"}

# Word boundary regex template used when compiling matchers for slugs
WORD_BOUNDARY = r"(?<![A-Za-z0-9_]){term}(?![A-Za-z0-9_])"


@dataclass(frozen=True)
class LinkInsertion:
    """Details about a link that was inserted into the HTML output."""

    term: str
    url: str
    priority: bool
    context: str | None = None


@dataclass(frozen=True)
class _TermMatcher:
    """Compiled regex and metadata for a single keyword replacement."""

    pattern: re.Pattern[str]
    key: str
    url: str
    display_term: str
    priority: bool


def fetch_sitemap_text(url: str, timeout: int = 15) -> str | None:
    """Fetch a sitemap from the given URL and return its decoded text.

    This function attempts to retrieve the contents of the provided URL
    using ``urllib.request`` with a modest timeout. If the file appears
    to be gzipped (either via its extension or content type), it is
    transparently decompressed. Any errors during the request are
    swallowed and result in ``None`` being returned.

    Parameters
    ----------
    url:
        The absolute URL of the sitemap or sitemap index to fetch.
    timeout:
        Timeout (in seconds) for the HTTP request.

    Returns
    -------
    str or None
        The decoded text of the sitemap if successful; otherwise ``None``.
    """

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
            content_type = resp.headers.get('Content-Type', '')
            # Decompress if .gz extension or gzip content type
            if url.lower().endswith('.gz') or 'application/x-gzip' in content_type:
                try:
                    data = gzip.decompress(data)
                except OSError:
                    pass
            # Try decoding as UTF-8, fall back to apparent encoding
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                encoding = resp.headers.get_content_charset() or 'utf-8'
                return data.decode(encoding, errors='replace')
    except Exception:
        return None


def parse_sitemap(xml_text: str, fetch_nested: bool = True) -> List[str]:
    """Parse a sitemap XML document and return a list of URLs.

    The function handles both standard ``<urlset>`` sitemaps and
    ``<sitemapindex>`` files which list additional sitemaps. When
    encountering nested sitemap locations in a ``<sitemapindex>``, it
    will fetch and parse each child sitemap recursively unless
    ``fetch_nested`` is set to ``False``.

    Parameters
    ----------
    xml_text:
        The raw XML content of the sitemap.
    fetch_nested:
        When ``True``, nested sitemaps referenced in a ``<sitemapindex>``
        will be fetched and parsed. Set to ``False`` to disable recursion.

    Returns
    -------
    list of str
        A flat list of URLs extracted from the sitemap(s). Invalid
        documents yield an empty list.
    """
    urls: List[str] = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return urls
    tag_lower = root.tag.lower()
    # Collect all <loc> tags regardless of namespace
    loc_elems = root.findall('.//{*}loc')
    if tag_lower.endswith('sitemapindex') and fetch_nested:
        for loc in loc_elems:
            loc_url = (loc.text or '').strip()
            if not loc_url:
                continue
            nested = fetch_sitemap_text(loc_url)
            if nested:
                # Do not recurse infinitely: only one level deep
                urls.extend(parse_sitemap(nested, fetch_nested=False))
    else:
        for loc in loc_elems:
            u = (loc.text or '').strip()
            if u:
                urls.append(u)
    return urls


def normalize_slug_from_url(url: str) -> Tuple[str, str]:
    """Derive a raw and normalized slug from a URL path segment.

    The raw slug is the final non-empty segment of the URL path with
    trailing slashes removed. The normalised slug converts hyphens and
    underscores to spaces and lowercases the string for keyword matching.

    Parameters
    ----------
    url:
        The absolute URL from which to extract the slug.

    Returns
    -------
    tuple of (raw_slug, normalized_slug)
        The original segment and a lowercase, space-separated version.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    segment = path.split('/')[-1] if path else ''
    raw = segment
    normalized = raw.replace('-', ' ').replace('_', ' ').lower()
    return raw, normalized


def build_link_map(domain: Domain) -> Dict[str, str]:
    """Construct a mapping from normalised slugs to their canonical URLs.

    Given a ``Domain`` instance, this helper inspects all associated
    ``Link`` objects and returns a dictionary keyed by the normalised slug
    (as stored in the ``slug`` field) with values equal to the link's URL.

    Parameters
    ----------
    domain:
        The domain for which to build the mapping.

    Returns
    -------
    dict[str, str]
        A mapping from lowercased, space-normalised slugs to absolute
        URLs. In case of duplicates, the latest link wins.
    """
    slug_to_url: Dict[str, str] = {}
    for link in domain.links.all():  # type: ignore[attr-defined]
        slug_to_url[link.slug] = link.url
    return slug_to_url


def strip_existing_links_from_html(html: str) -> str:
    """Remove anchor tags from ``html`` while preserving their inner content."""

    if not html:
        return html

    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        soup = BeautifulSoup(html, 'html.parser')

    for anchor in soup.find_all('a'):
        anchor.unwrap()

    return str(soup)


def _normalize_term(term: str) -> str:
    """Return a lowercase, single-space version of ``term`` for lookups."""

    return re.sub(r"\s+", " ", term.strip().lower())


def _clean_display_term(term: str) -> str:
    """Collapse internal whitespace but preserve the original casing."""

    return re.sub(r"\s+", " ", term.strip())


def _build_term_matchers(
    slug_to_url: Dict[str, str],
    priority_pairs: Sequence[tuple[str, str]],
) -> List[_TermMatcher]:
    """Combine priority entries with sitemap slugs into regex matchers."""

    matchers: List[_TermMatcher] = []
    seen_keys: set[str] = set()

    # Add user-specified priority pairs first, respecting their order.
    for term, url in priority_pairs:
        display = _clean_display_term(term)
        if not display:
            continue
        key = _normalize_term(display)
        if key in seen_keys:
            continue
        pattern = re.compile(WORD_BOUNDARY.format(term=re.escape(display)), flags=re.IGNORECASE)
        matchers.append(_TermMatcher(pattern=pattern, key=key, url=url, display_term=display, priority=True))
        seen_keys.add(key)

    # Next process automatic slugs, preferring longer phrases first.
    sortable: List[Tuple[str, str]] = []
    for slug, url in slug_to_url.items():
        display = _clean_display_term(slug)
        if not display:
            continue
        sortable.append((display, url))

    sortable.sort(key=lambda item: (-len(item[0]), item[0]))

    for display, url in sortable:
        key = _normalize_term(display)
        if key in seen_keys:
            continue
        pattern = re.compile(WORD_BOUNDARY.format(term=re.escape(display)), flags=re.IGNORECASE)
        matchers.append(_TermMatcher(pattern=pattern, key=key, url=url, display_term=display, priority=False))
        seen_keys.add(key)

    return matchers


def _extract_context_snippet(text: str, match: re.Match[str], window: int = 45) -> str:
    """Return a trimmed snippet of ``text`` surrounding the match."""

    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    snippet = text[start:end].strip()
    return re.sub(r"\s+", " ", snippet)


def _should_skip(node: NavigableString) -> bool:
    """Determine whether a text node is within a tag that should be skipped.

    Walks up the tree from the given text node and returns ``True`` if any
    ancestor has a tag name contained in ``SKIP_TAGS``. This ensures we
    never insert links within headings, code blocks or existing anchors.

    Parameters
    ----------
    node:
        A BeautifulSoup ``NavigableString`` whose parent chain will be
        inspected.

    Returns
    -------
    bool
        ``True`` if the node should be skipped, otherwise ``False``.
    """
    parent = node.parent
    while parent is not None and getattr(parent, 'name', None):
        if parent.name and parent.name.lower() in SKIP_TAGS:
            return True
        parent = parent.parent
    return False


def interlink_html(
    html: str,
    slug_to_url: Dict[str, str],
    max_links: int = 10,
    *,
    priority_pairs: Sequence[tuple[str, str]] | None = None,
    max_links_per_block: int = 3,
) -> Tuple[str, List[LinkInsertion]]:
    """Insert anchors for matching keywords and return the enriched HTML.

    The function processes paragraph-style content, prioritising user
    supplied ``priority_pairs`` before falling back to automatically
    discovered sitemap slugs. Each keyword is linked at most once, the
    matching is case-insensitive, and tags such as headers and code blocks
    are deliberately skipped to preserve readability.

    Parameters
    ----------
    html:
        The HTML content into which links should be injected.
    slug_to_url:
        Mapping of normalised sitemap slugs to canonical URLs.
    max_links:
        Overall cap on links to insert.
    priority_pairs:
        Optional sequence of ``(keyword, url)`` tuples that should be
        linked ahead of automatic suggestions.
    max_links_per_block:
        Soft limit for automatic links inside a single text block (priority
        links ignore this budget). Helps avoid overlinking inside one
        paragraph.

    Returns
    -------
    tuple
        ``(html, inserted)`` where ``html`` is the enriched markup and
        ``inserted`` is a list of :class:`LinkInsertion` metadata.
    """

    if not html:
        return html, []

    pairs = priority_pairs or []
    matchers = _build_term_matchers(slug_to_url, pairs)
    if not matchers:
        return html, []

    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        # Fallback to html.parser if lxml isn't installed
        soup = BeautifulSoup(html, 'html.parser')

    block_tags = ['p', 'li', 'blockquote']
    blocks = soup.find_all(block_tags)
    if not blocks:
        blocks = [soup]

    linked_keys: set[str] = set()
    inserted: List[LinkInsertion] = []
    link_count = 0
    per_block_limit = max(1, min(max_links, max_links_per_block))

    for block in blocks:
        if link_count >= max_links:
            break

        block_links = 0
        for text_node in list(block.descendants):
            if link_count >= max_links:
                break
            if not isinstance(text_node, NavigableString):
                continue
            if _should_skip(text_node):
                continue

            original = str(text_node)
            if not original or not original.strip():
                continue

            for matcher in matchers:
                if matcher.key in linked_keys:
                    continue
                if not matcher.priority and block_links >= per_block_limit:
                    continue

                match = matcher.pattern.search(original)
                if not match:
                    continue

                after = original[match.end():]
                if after:
                    text_node.insert_after(after)

                anchor = soup.new_tag('a', href=matcher.url)
                anchor['class'] = ['interlinked-anchor']
                anchor['data-source'] = 'priority' if matcher.priority else 'auto'
                anchor.string = match.group(0)
                text_node.insert_after(anchor)

                before = original[:match.start()]
                if before:
                    text_node.replace_with(before)
                else:
                    text_node.extract()

                linked_keys.add(matcher.key)
                link_count += 1
                block_links += 1

                context = _extract_context_snippet(original, match) or None
                inserted.append(
                    LinkInsertion(
                        term=matcher.display_term,
                        url=matcher.url,
                        priority=matcher.priority,
                        context=context,
                    )
                )

                break

    return str(soup), inserted
