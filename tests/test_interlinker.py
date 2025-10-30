from __future__ import annotations

import textwrap
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from interlinker.forms import InterlinkForm
from interlinker.middleware import SlidingWindowRateThrottle
from interlinker.models import Domain, InterlinkGeneration, Link
from interlinker.services import LinkInsertion, build_link_map, interlink_html, parse_sitemap


class InterlinkFormTests(TestCase):
    def setUp(self) -> None:
        self.domain = Domain.objects.create(base_url='https://example.com', hostname='example.com')

    def form(self, **overrides):
        data = {
            'domain': self.domain.pk,
            'content': 'Example content',
            'max_links': 5,
            'is_html_input': False,
            'priority_pairs': '',
        }
        data.update(overrides)
        return InterlinkForm(data)

    def test_priority_pairs_parses_multiple_separators(self) -> None:
        form = self.form(priority_pairs=textwrap.dedent(
            """
            Primary Term -> https://example.com/primary
            secondary term | https://example.com/secondary
            Tertiary Term, https://example.com/tertiary
            
            duplicate term -> https://example.com/one
            duplicate term -> https://example.com/two
            """
        ).strip())
        self.assertTrue(form.is_valid(), form.errors)
        parsed = form.cleaned_data['priority_pairs']
        self.assertEqual(
            parsed,
            [
                ('Primary Term', 'https://example.com/primary'),
                ('secondary term', 'https://example.com/secondary'),
                ('Tertiary Term', 'https://example.com/tertiary'),
                ('duplicate term', 'https://example.com/one'),
            ],
        )

    def test_priority_pairs_requires_separator(self) -> None:
        form = self.form(priority_pairs='Missing separator line')
        self.assertFalse(form.is_valid())
        self.assertIn('Priority line 1', form.errors['priority_pairs'][0])


class SitemapServiceTests(TestCase):
    def test_parse_sitemap_basic(self) -> None:
        xml = textwrap.dedent(
            """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>https://example.com/one</loc></url>
                <url><loc>https://example.com/two</loc></url>
            </urlset>
            """
        ).strip()

        urls = parse_sitemap(xml, fetch_nested=False)
        self.assertEqual(urls, ['https://example.com/one', 'https://example.com/two'])

    @patch('interlinker.services.fetch_sitemap_text')
    def test_parse_sitemap_fetches_nested_indexes(self, mock_fetch) -> None:
        parent = textwrap.dedent(
            """
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <sitemap><loc>https://example.com/child.xml</loc></sitemap>
            </sitemapindex>
            """
        ).strip()
        child = textwrap.dedent(
            """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>https://example.com/child</loc></url>
            </urlset>
            """
        ).strip()
        mock_fetch.return_value = child

        urls = parse_sitemap(parent, fetch_nested=True)
        self.assertEqual(urls, ['https://example.com/child'])
        mock_fetch.assert_called_once_with('https://example.com/child.xml')

    def test_build_link_map_returns_slug_mapping(self) -> None:
        domain = Domain.objects.create(base_url='https://example.com', hostname='example.com')
        Link.objects.create(domain=domain, url='https://example.com/one', slug='first slug', raw_slug='first-slug')
        Link.objects.create(domain=domain, url='https://example.com/two', slug='second slug', raw_slug='second-slug')

        mapping = build_link_map(domain)
        self.assertEqual(
            mapping,
            {
                'first slug': 'https://example.com/one',
                'second slug': 'https://example.com/two',
            },
        )


class InterlinkServiceTests(TestCase):
    def test_interlink_html_prioritises_priority_terms(self) -> None:
        html = '<p>Priority phrase leads the way.</p><p>Meanwhile, the automatic term waits here.</p>'
        slug_map = {'automatic term': 'https://example.com/auto'}
        priority_pairs = [('Priority phrase', 'https://example.com/priority')]

        rendered, inserted = interlink_html(
            html,
            slug_to_url=slug_map,
            max_links=5,
            priority_pairs=priority_pairs,
        )

        self.assertIn('href="https://example.com/priority"', rendered)
        self.assertIn('href="https://example.com/auto"', rendered)
        self.assertEqual(
            inserted,
            [
                LinkInsertion(
                    term='Priority phrase',
                    url='https://example.com/priority',
                    priority=True,
                    context='Priority phrase leads the way.',
                ),
                LinkInsertion(
                    term='automatic term',
                    url='https://example.com/auto',
                    priority=False,
                    context='Meanwhile, the automatic term waits here.',
                ),
            ],
        )


class UploadSitemapViewTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_upload_sitemap_via_file_creates_links(self) -> None:
        xml = textwrap.dedent(
            """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>https://example.com/alpha</loc></url>
                <url><loc>https://example.com/beta</loc></url>
            </urlset>
            """
        ).strip()
        uploaded = SimpleUploadedFile('sitemap.xml', xml.encode('utf-8'), content_type='text/xml')

        response = self.client.post(
            reverse('interlinker:sitemap_upload'),
            data={
                'base_url': 'https://example.com',
                'file': uploaded,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('interlinker:sitemap_links'))
        self.assertEqual(Domain.objects.count(), 1)
        self.assertEqual(Link.objects.count(), 2)

    @patch('interlinker.views.fetch_sitemap_text')
    def test_upload_sitemap_via_url_fetches_and_creates_domain(self, mock_fetch) -> None:
        mock_fetch.return_value = textwrap.dedent(
            """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>https://example.com/gamma</loc></url>
            </urlset>
            """
        ).strip()

        response = self.client.post(
            reverse('interlinker:sitemap_upload'),
            data={
                'sitemap_url': 'https://example.com/sitemap.xml',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Domain.objects.count(), 1)
        domain = Domain.objects.get()
        self.assertEqual(domain.base_url, 'https://example.com')
        self.assertEqual(Link.objects.count(), 1)
        mock_fetch.assert_called_once_with('https://example.com/sitemap.xml')


class RateLimitMiddlewareTests(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    @override_settings(THROTTLED_ROUTES=['sample:action'])
    def test_rate_limit_blocks_after_threshold(self) -> None:
        responses = []

        def handler(request):
            responses.append(request)
            from django.http import HttpResponse

            return HttpResponse('OK')

        middleware = SlidingWindowRateThrottle(handler, limit=2, window=60, key_prefix='test-rate')

        def build_request():
            req = self.factory.post('/sample-action/')
            req.resolver_match = SimpleNamespace(namespace='sample', url_name='action', view_name='sample:action')
            req.META['REMOTE_ADDR'] = '127.0.0.1'
            return req

        first = middleware(build_request())
        self.assertEqual(first.status_code, 200)
        second = middleware(build_request())
        self.assertEqual(second.status_code, 200)
        third = middleware(build_request())
        self.assertEqual(third.status_code, 429)

class InterlinkViewTests(TestCase):
    def setUp(self) -> None:
        self.client: Client = Client()
        self.user = get_user_model().objects.create_user(
            username='tester',
            email='tester@example.com',
            password='password123',
        )
        self.domain = Domain.objects.create(base_url='https://example.com', hostname='example.com')
        self.link = Link.objects.create(
            domain=self.domain,
            url='https://example.com/priority',
            slug='priority phrase',
            raw_slug='priority-phrase',
        )
        self.client.login(username='tester', password='password123')

    def test_interlink_post_creates_generation_and_renders_result(self) -> None:
        response = self.client.post(
            reverse('interlinker:interlink'),
            data={
                'domain': self.domain.pk,
                'content': 'This Priority Phrase should link automatically.',
                'max_links': 5,
                'is_html_input': 'on',
                'priority_pairs': 'Priority Phrase -> https://example.com/custom',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interlinker/interlink_result.html')
        generation = InterlinkGeneration.objects.get(user=self.user)
        self.assertEqual(generation.domain, self.domain)
        self.assertEqual(generation.inserted_total, 1)
        self.assertEqual(generation.inserted_priority, 1)
        self.assertEqual(generation.priority_pairs[0]['url'], 'https://example.com/custom')

    def test_history_requires_login(self) -> None:
        self.client.logout()
        url = reverse('interlinker:history')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_history_lists_generations(self) -> None:
        InterlinkGeneration.objects.create(
            user=self.user,
            domain=self.domain,
            source_excerpt='Excerpt',
            linked_html='<p>linked</p>',
            inserted_total=2,
            inserted_priority=1,
            inserted_auto=1,
            max_links=5,
            source_is_html=True,
            priority_pairs=[
                {
                    'term': 'Priority Phrase',
                    'url': 'https://example.com/custom',
                }
            ],
            inserted_records=[
                {
                    'term': 'Priority Phrase',
                    'url': 'https://example.com/custom',
                    'priority': True,
                    'context': 'Excerpt',
                }
            ],
        )
        response = self.client.get(reverse('interlinker:history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Priority Phrase')
        self.assertContains(response, 'linked')
