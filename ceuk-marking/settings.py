"""
Django settings for crowdsourcer project.

Generated by 'django-admin startproject' using Django 4.1.4.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/
"""

import logging
import socket
import sys
from pathlib import Path

import environ

TEST_MODE = False
# turn off logging during tests as otherwise we get file not found errors
if len(sys.argv) > 1 and sys.argv[1] == "test":
    TEST_MODE = True

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    HIDE_DEBUG_TOOLBAR=(bool, False),
    LOG_LEVEL=(str, "WARNING"),
    BRAND=(str, "default"),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CACHE_FILE = env("CACHE_FILE")
HIDE_DEBUG_TOOLBAR = env("HIDE_DEBUG_TOOLBAR")
MAPIT_URL = env("MAPIT_URL")
MAPIT_API_KEY = env("MAPIT_API_KEY")
LOG_LEVEL = env("LOG_LEVEL")
BRAND = env("BRAND")

# make sure CSRF checking still works behind load balancers
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

PASSWORD_RESET_TIMEOUT = 8 * 24 * 60 * 60

if env.str("BUGS_EMAIL", None):  # pragma: no cover
    SERVER_EMAIL = env("BUGS_EMAIL")
    ADMINS = (("mySociety bugs", env("BUGS_EMAIL")),)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# Application definition


if len(sys.argv) > 1 and sys.argv[1] == "test":
    logging.disable(logging.CRITICAL)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "compressor",
    "django_bootstrap5",
    "crowdsourcer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "crowdsourcer.middleware.AddStateMiddleware",
]

ROOT_URLCONF = "ceuk-marking.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ceuk-marking.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

DATABASES = {"default": env.db()}


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / ".static"

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
)

STATICFILES_DIRS = [
    BASE_DIR / "crowdsourcer" / "static",
    ("bootstrap", BASE_DIR / "vendor" / "bootstrap" / "scss"),
    ("bootstrap", BASE_DIR / "vendor" / "bootstrap" / "js"),
    ("jquery", BASE_DIR / "vendor" / "jquery" / "js"),
]

# only want to do this for live really
if not DEBUG:  # pragma: no cover
    STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    )

COMPRESS_PRECOMPILERS = (("text/x-scss", "django_libsass.SassCompiler"),)
COMPRESS_CSS_HASHING_METHOD = "content"

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Sending messages
EMAIL_HOST = env.str("EMAIL_HOST", "localhost")
EMAIL_PORT = env.str("EMAIL_PORT", 1025)
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", "webmaster@localhost")

if not TEST_MODE:
    LOG_FILE = BASE_DIR / "applogs" / "logfile.log"

    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "filename": LOG_FILE,
                "formatter": "verbose",
            },
        },
        "loggers": {
            "crowdsourcer": {
                "handlers": ["file"],
                "propagate": True,
                "level": LOG_LEVEL,
            },
        },
    }

if DEBUG and HIDE_DEBUG_TOOLBAR is False:  # pragma: no cover
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [ip[:-1] + "1" for ip in ips] + ["127.0.0.1", "10.0.2.2"]
    CSRF_TRUSTED_ORIGINS = ["https://*.preview.app.github.dev"]

    # debug toolbar has to come after django_hosts middleware
    MIDDLEWARE.insert(1, "debug_toolbar.middleware.DebugToolbarMiddleware")

    INSTALLED_APPS += ("debug_toolbar",)

    DEBUG_TOOLBAR_PANELS = [
        "debug_toolbar.panels.versions.VersionsPanel",
        "debug_toolbar.panels.timer.TimerPanel",
        "debug_toolbar.panels.settings.SettingsPanel",
        "debug_toolbar.panels.headers.HeadersPanel",
        "debug_toolbar.panels.request.RequestPanel",
        "debug_toolbar.panels.sql.SQLPanel",
        "debug_toolbar.panels.staticfiles.StaticFilesPanel",
        "debug_toolbar.panels.templates.TemplatesPanel",
        "debug_toolbar.panels.cache.CachePanel",
        "debug_toolbar.panels.signals.SignalsPanel",
        "debug_toolbar.panels.logging.LoggingPanel",
        "debug_toolbar.panels.redirects.RedirectsPanel",
    ]

BOOTSTRAP5 = {
    "wrapper_class": "mb-3 mb-md-4",
    "set_placeholder": False,
}
