"""
Django settings for the interlinker_tool.

This file contains only a minimal configuration sufficient to get the
sample application working. The project uses SQLite for its database,
includes the interlinker app along with the standard Django contrib apps,
and serves static files from a ``static`` directory at the project root.

Please consult the Django documentation for additional configuration
options: https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-me')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() == 'true'

RUNNING_TESTS = os.getenv('PYTEST_CURRENT_TEST') is not None
if RUNNING_TESTS:
    DEBUG = True

if not DEBUG and SECRET_KEY == 'django-insecure-change-me' and not RUNNING_TESTS:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set when DEBUG is False.')

ALLOWED_HOSTS: list[str] = [
    host.strip()
    for host in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
    if host.strip()
]

CSRF_TRUSTED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'axes',
    'interlinker',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'interlinker.middleware.sliding_window_rate_throttle',
]

ROOT_URLCONF = 'interlinker_tool.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'interlinker_tool.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases


def _database_config_from_url(
    url: str,
    *,
    conn_max_age: int,
    ssl_require: bool,
    sqlite_default: Path,
) -> dict[str, object]:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    if scheme in {'postgres', 'postgresql'}:
        engine = 'django.db.backends.postgresql'
        name = unquote(parsed.path.lstrip('/')) or ''
    elif scheme in {'mysql', 'mariadb'}:
        engine = 'django.db.backends.mysql'
        name = unquote(parsed.path.lstrip('/')) or ''
    elif scheme == 'sqlite':
        engine = 'django.db.backends.sqlite3'
        raw_path = unquote(parsed.path or '')
        if raw_path.startswith('/'):
            raw_path = raw_path[1:]
        candidate = raw_path or str(sqlite_default)
        if os.path.isabs(candidate):
            name = candidate
        else:
            name = str((sqlite_default.parent / candidate).resolve())
    else:
        raise ImproperlyConfigured(f'Unsupported DATABASE_URL scheme: {scheme}')

    config: dict[str, object] = {
        'ENGINE': engine,
        'NAME': name,
        'CONN_MAX_AGE': conn_max_age,
    }

    if parsed.username:
        config['USER'] = unquote(parsed.username)
    if parsed.password:
        config['PASSWORD'] = unquote(parsed.password)
    if parsed.hostname:
        config['HOST'] = parsed.hostname
    if parsed.port:
        config['PORT'] = str(parsed.port)

    query_options = {key: values[-1] for key, values in parse_qs(parsed.query).items() if values}
    if (
        engine != 'django.db.backends.sqlite3'
        and ssl_require
        and query_options.get('sslmode', '').lower() != 'require'
    ):
        query_options.setdefault('sslmode', 'require')

    if query_options:
        config['OPTIONS'] = query_options

    return config


default_sqlite_path = BASE_DIR / 'db.sqlite3'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': default_sqlite_path,
    }
}

database_url = os.getenv('DATABASE_URL')
if database_url:
    conn_max_age = int(os.getenv('DATABASE_CONN_MAX_AGE', '600'))
    ssl_require = os.getenv('DATABASE_SSL_REQUIRE', 'true').lower() == 'true'
    DATABASES['default'] = _database_config_from_url(
        database_url,
        conn_max_age=conn_max_age,
        ssl_require=ssl_require,
        sqlite_default=default_sqlite_path,
    )

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = os.getenv('DJANGO_STATIC_URL', '/static/')

STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = Path(os.getenv('DJANGO_STATIC_ROOT', BASE_DIR / 'staticfiles'))

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_KEEP_ONLY_HASHED_FILES = True

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication redirects
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'interlinker:interlink'
LOGOUT_REDIRECT_URL = 'interlinker:home'


# django-axes configuration: guard against brute-force login attempts
AXES_FAILURE_LIMIT = 6
AXES_COOLOFF_TIME = 1  # hour(s)
AXES_ENABLE_ADMIN = True
AXES_RESET_ON_SUCCESS = True
AXES_ONLY_ADMIN_SITE = False
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']


# Security headers and session hardening
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = os.getenv('DJANGO_SESSION_COOKIE_SECURE', 'false').lower() == 'true'
CSRF_COOKIE_SECURE = os.getenv('DJANGO_CSRF_COOKIE_SECURE', 'false').lower() == 'true'
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv('DJANGO_SECURE_SSL_REDIRECT', 'true').lower() == 'true'
    SESSION_COOKIE_SECURE = os.getenv('DJANGO_SESSION_COOKIE_SECURE', 'true').lower() == 'true'
    CSRF_COOKIE_SECURE = os.getenv('DJANGO_CSRF_COOKIE_SECURE', 'true').lower() == 'true'
    SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_SSL_REDIRECT = False

# Rate limiting / throttling defaults (per IP per route)
THROTTLED_ROUTES = [
    'interlinker:interlink',
    'interlinker:sitemap_upload',
    'interlinker:signup',
    'login',
]
THROTTLE_LIMIT = int(os.getenv('INTERLINKER_THROTTLE_LIMIT', '60'))
THROTTLE_WINDOW = int(os.getenv('INTERLINKER_THROTTLE_WINDOW', '60'))
THROTTLE_IP_HEADER = os.getenv('INTERLINKER_THROTTLE_HEADER', 'HTTP_X_FORWARDED_FOR')
THROTTLE_KEY_PREFIX = 'interlinker:throttle'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'axes.backends.AxesBackend',
]


log_level = os.getenv('DJANGO_LOG_LEVEL', 'INFO').upper()
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': log_level,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': log_level,
            'propagate': False,
        },
        'axes': {
            'handlers': ['console'],
            'level': log_level,
            'propagate': False,
        },
    },
}
