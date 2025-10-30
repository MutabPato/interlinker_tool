"""Forms for the interlinker app.

The forms define user-facing inputs for uploading sitemaps and interlinking
blog/review content. Validation rules ensure sensible defaults and required
fields.
"""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

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
        widget=forms.Textarea(
            attrs={
                'rows': 18,
                'placeholder': 'Paste the article body or HTML snippet you want to enrich...'
            }
        ),
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
    strip_existing_links = forms.BooleanField(
        required=False,
        label='Remove existing links',
        help_text='Strip <a> tags from the content before adding new links.'
    )
    priority_pairs = forms.CharField(
        required=False,
        label='Priority keywords',
        widget=forms.Textarea(
            attrs={
                'rows': 4,
                'placeholder': 'product comparison -> https://example.com/buy\nsecondary phrase -> https://example.com/guide',
            }
        ),
        help_text=(
            'Optional. Provide one keyword and URL per line using "keyword -> https://example.com". '
            'Priority links are inserted before automatic suggestions.'
        ),
    )

    def clean_priority_pairs(self) -> list[tuple[str, str]]:
        """Parse newline-delimited ``keyword -> url`` pairs into tuples."""

        raw_value = self.cleaned_data.get('priority_pairs', '')
        if not raw_value:
            return []

        url_field = forms.URLField()
        parsed: list[tuple[str, str]] = []
        seen_terms: set[str] = set()
        separators = ('->', '|', ',', '\t')

        for index, line in enumerate(raw_value.splitlines(), start=1):
            candidate = line.strip()
            if not candidate:
                continue
            term_part = None
            url_part = None
            for sep in separators:
                if sep in candidate:
                    term_part, url_part = (piece.strip() for piece in candidate.split(sep, 1))
                    break
            if term_part is None or url_part is None:
                raise forms.ValidationError(
                    f'Priority line {index} must include a keyword and URL separated by ->, |, or ,.'
                )
            if not term_part:
                raise forms.ValidationError(f'Priority line {index} is missing a keyword.')
            try:
                cleaned_url = url_field.clean(url_part)
            except forms.ValidationError as exc:
                raise forms.ValidationError(
                    f'Priority line {index} has an invalid URL: {exc.messages[0]}'
                ) from exc
            term_key = term_part.lower()
            if term_key in seen_terms:
                continue
            seen_terms.add(term_key)
            parsed.append((term_part, cleaned_url))

        return parsed


class LoginForm(AuthenticationForm):
    """Authentication form with placeholder hints to match the UI."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'autofocus': True,
            'placeholder': 'you@example.com or username',
        })
        self.fields['password'].widget.attrs.update({
            'placeholder': 'Your password',
        })


class SignUpForm(UserCreationForm):
    """User signup form asking for email and password confirmation."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
        help_text='We use your email to send password resets and account notices.',
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'placeholder': 'username'})
        self.fields['password1'].widget.attrs.update({'placeholder': 'Create password'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Repeat password'})

    def save(self, commit: bool = True):  # type: ignore[override]
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user
