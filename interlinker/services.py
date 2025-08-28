"""Service functions for ingesting sitemaps and interlinking text.

These functions encapsulate the core logic of the application so they
can be easily unit tested and reused from the views. They handle
fetching and parsing sitemap XML, normalising slugs from URLs, building
a slug→URL map from stored links, and inserting anchor tags into HTML
content based on keywords.
"""

from __future__ import annotations

import gzip
import io
import re
import urllib.request
from typing import Dict, Iterable, List, Tuple
from xml.etree import ElementTree

from bs4 import BeautifulSoup, NavigableString  # type: ignore

from .models import Domain

# Tags inside which links should never be inserted
SKIP_TAGS: set[str] = {"a", "code", "pre", "h1", "h2", "h3"}

# Word boundary regex template used when compiling matchers for slugs
WORD_BOUNDARY = r"(?<![A-Za-z0-9_]){term}(?![A-Za-z0-9_])"


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


def _compile_patterns(terms: Iterable[str]) -> List[Tuple[re.Pattern[str], str]]:
    """Compile regex patterns for a list of search terms.

    Longer terms are prioritised by sorting the list in descending order of
    length, preventing shorter terms from matching inside longer phrases.

    Parameters
    ----------
    terms:
        An iterable of normalised slug terms to be converted into regex
        patterns.

    Returns
    -------
    list of tuple
        Each tuple contains a compiled regular expression and its
        corresponding term.
    """
    unique = sorted(set(terms), key=lambda s: (-len(s), s))
    patterns: List[Tuple[re.Pattern[str], str]] = []
    for term in unique:
        escaped = re.escape(term)
        pat = re.compile(WORD_BOUNDARY.format(term=escaped), flags=re.IGNORECASE)
        patterns.append((pat, term))
    return patterns


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


def interlink_html(html: str, slug_to_url: Dict[str, str], max_links: int = 10) -> str:
    """Insert anchor tags into HTML for keywords matched in slug_to_url.

    The function scans through paragraph-like blocks (``<p>`` and ``<li>``
    elements) and replaces the first occurrence of each keyword (slug) with
    an anchor tag pointing to the associated URL. Matching is done on
    whole-word boundaries and is case-insensitive. A global limit on
    inserted links prevents overlinking. If a keyword appears multiple
    times, only the first occurrence is linked.

    Parameters
    ----------
    html:
        The HTML content into which links should be injected. This may
        contain arbitrary markup.
    slug_to_url:
        A mapping of normalised keywords to their target URLs. Only the
        keys of this mapping are considered for linking.
    max_links:
        The maximum number of links to insert. Once this limit is
        reached no further replacements are attempted.

    Returns
    -------
    str
        The modified HTML with anchor tags inserted. If ``slug_to_url``
        is empty or no matches are found, the original HTML is returned.
    """
    if not slug_to_url or not html:
        return html

    # Build patterns for each slug, prioritising longer phrases
    patterns = _compile_patterns(slug_to_url.keys())

    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        # Fallback to html.parser if lxml isn't installed
        soup = BeautifulSoup(html, 'html.parser')

    blocks = soup.find_all(['p', 'li'])
    linked_terms: set[str] = set()
    link_count = 0

    for block in blocks:
        if link_count >= max_links:
            break
        # Iterate over all descendant text nodes for potential replacement
        for text_node in list(block.descendants):
            if link_count >= max_links:
                break
            if not isinstance(text_node, NavigableString):
                continue
            if _should_skip(text_node):
                continue
            original = str(text_node)
            replaced = original
            # Try each pattern until a match is made or exhausted
            for pat, term in patterns:
                if term in linked_terms:
                    continue
                m = pat.search(replaced)
                if m:
                    target = slug_to_url.get(term)
                    if not target:
                        continue
                    anchor = f'<a href="{target}">{m.group(0)}</a>'
                    # Replace only the first occurrence
                    replaced = pat.sub(anchor, replaced, count=1)
                    linked_terms.add(term)
                    link_count += 1
                    break
            if replaced != original:
                try:
                    new_fragment = BeautifulSoup(replaced, 'lxml')
                except Exception:
                    new_fragment = BeautifulSoup(replaced, 'html.parser')
                text_node.replace_with(new_fragment)
            if link_count >= max_links:
                break

    return str(soup)