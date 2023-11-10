"""
Django settings for coriolis project.

Generated by 'django-admin startproject' using Django 3.2.9.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

import os
import socket
from pathlib import Path

import environ

from payments_przelewy24.config import Przelewy24Config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ----- Environment Setup -----

env = environ.Env()
env.read_env(env.str("ENV_PATH", default=".env"))

# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/
SECRET_KEY = env.str("SECRET_KEY", "what-a-horribly-insecure-world-is-this")
ENVIRONMENT = env.str("ENVIRONMENT", "development")
DEBUG = env.bool("DEBUG", True)

dsn = env.str("SENTRY_DSN", None)
if not DEBUG and dsn:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=ENVIRONMENT,
        integrations=[DjangoIntegration()],
        send_default_pii=env.bool("SENTRY_SEND_PII", True),  # Send user details, etc?
        traces_sample_rate=env.float("SENTRY_SAMPLE_RATE", 1.0),  # Ratio of transactions to monitor for perf issues.
        _experiments={
            # Let's see what's slow.
            "profiles_sample_rate": 1.0,
        },
    )

# Database: https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DATABASES = {"default": env.db()}

# Redis for Dramatiq and caching
REDIS_URL = env.str("REDIS_URL")

# Email: https://docs.djangoproject.com/en/4.2/ref/settings/#email-backend
DRAMATIQ_EMAIL_BACKEND = env.str("DRAMATIQ_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_BACKEND = env.str("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env.str("EMAIL_HOST", "localhost")
EMAIL_PORT = env.int("EMAIL_PORT", 25)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", False)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", False)

SERVER_EMAIL = env.str("SERVER_EMAIL", "coriolis@localhost")
DEFAULT_FROM_EMAIL = SERVER_EMAIL

MEDIA_ROOT = env.str("MEDIA_ROOT", BASE_DIR / "media")
MEDIA_URL = env.str("MEDIA_URL", "/media/")

TICKET_RENDERER_MAX_JOBS = env.int("TICKET_RENDERER_MAX_JOBS", 3)

hosts = env.str("ALLOWED_HOSTS", None)
if hosts:
    ALLOWED_HOSTS = [host.strip() for host in hosts.split(",")]

phone_region = env.str("PHONENUMBER_REGION", None)
if phone_region:
    PHONENUMBER_DEFAULT_REGION = phone_region

# Pretty-print all phone numbers:
PHONENUMBER_DEFAULT_FORMAT = "INTERNATIONAL"

CURRENCY = env.str("CURRENCY", "EUR")
TIME_ZONE = env.str("TIME_ZONE", "Etc/UTC")
LANGUAGE_CODE = env.str("LANGUAGE_CODE", "en-us")

LOGIN_NOTICE = env.str("LOGIN_NOTICE", None)
LOGIN_FOOTER = env.str("LOGIN_FOOTER", None)
COOKIES_POLICY_LINK = env.str("COOKIES_POLICY_LINK", None)

CUSTOM_PASSWORD_LIST = env.str("CUSTOM_PASSWORD_LIST", None)

PAYMENT_HOST = env.str("PAYMENT_HOST", "localhost:8000")
PAYMENT_USES_SSL = env.bool("PAYMENT_HTTPS", not DEBUG)  # Enforce HTTPS on production envs.
PAYMENT_MODEL = "events.Payment"
PAYMENT_VARIANTS = {
    "default": ("payments.dummy.DummyProvider", {}),
    "przelewy24": (
        "payments_przelewy24.provider.Przelewy24Provider",
        {"config": Przelewy24Config.from_env()},
    ),
}

PAYMENT_MAX_ATTEMPTS = 5
PAYMENT_ISO_COUNTRY = env.str("PAYMENT_ISO_COUNTRY", "PL")
PAYMENT_PAY_ONLINE_VARIANT = env.str("PAYMENT_PAY_ONLINE_VARIANT", "default")

# --- STUFF BELOW THIS POINT SHOULD NOT BE CONFIGURABLE PER ENVIRONMENT. ---

if DEBUG:
    import os  # only if you haven't already imported this
    import socket  # only if you haven't already imported this

    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [ip[:-1] + "1" for ip in ips] + ["127.0.0.1", "10.0.2.2"]

# Application definition

# fmt: off
INSTALLED_APPS = [
    # Instead of 'django.contrib.admin' we use:
    "coriolis.apps.CoriolisAdminConfig",

    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    "django_dramatiq",
    "django_dramatiq_email",
    "dramatiq_crontab",

    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.discord",

    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "allauth_2fa",

    "hijack",
    "hijack.contrib.admin",

    "djmoney",
    "payments",
    "payments_przelewy24",

    "colorfield",
    "phonenumber_field",
    "crispy_forms",
    "crispy_bootstrap5",
    "debug_toolbar",

    "events",
]
# fmt: on

CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# fmt: off
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "events.middleware.ForceDefaultLanguageMiddleware",
    "django.middleware.locale.LocaleMiddleware",

    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "allauth_2fa.middleware.AllauthTwoFactorMiddleware",
    "events.middleware.RequireSuperuser2FAMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "hijack.middleware.HijackUserMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]
# fmt: on

DRAMATIQ_BROKER = {
    "BROKER": "dramatiq.brokers.redis.RedisBroker",
    "OPTIONS": {"url": REDIS_URL, "namespace": "coriolis-dramatiq-broker"},
    "MIDDLEWARE": [
        "dramatiq.middleware.Prometheus",
        "dramatiq.middleware.AgeLimit",
        "dramatiq.middleware.TimeLimit",
        "dramatiq.middleware.Callbacks",
        "dramatiq.middleware.Retries",
        "django_dramatiq.middleware.DbConnectionsMiddleware",
        "django_dramatiq.middleware.AdminMiddleware",
    ],
}

DRAMATIQ_RESULT_BACKEND = {
    "BACKEND": "dramatiq.results.backends.redis.RedisBackend",
    "BACKEND_OPTIONS": {"url": REDIS_URL, "namespace": "coriolis-dramatiq-results"},
    "MIDDLEWARE_OPTIONS": {"result_ttl": 60000},
}

# Disabled until the lock implementation is fixed in dramatiq-crontab:
# DRAMATIQ_CRONTAB = {"REDIS_URL": REDIS_URL}

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AUTH_USER_MODEL = "events.User"

ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_ADAPTER = "allauth_2fa.adapter.OTPAdapter"
SOCIALACCOUNT_LOGIN_ON_GET = True

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SITE_ID = 1
ROOT_URLCONF = "coriolis.urls"
WSGI_APPLICATION = "coriolis.wsgi.application"

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
                "events.context.global_listed_event_pages",
            ],
        },
    },
]

COMMON_PASSWORD_VALIDATOR_OPTIONS = {}
if CUSTOM_PASSWORD_LIST:
    COMMON_PASSWORD_VALIDATOR_OPTIONS["password_list_path"] = CUSTOM_PASSWORD_LIST

# Password validation: https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
        "OPTIONS": COMMON_PASSWORD_VALIDATOR_OPTIONS,
    },
]

# https://docs.djangoproject.com/en/4.1/topics/auth/passwords/#using-scrypt-with-django
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.ScryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

TICKET_PURCHASE_RATE_LIMIT_CACHE_NAME = "coriolis-ticket-purchase-rate-limits"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    },
    TICKET_PURCHASE_RATE_LIMIT_CACHE_NAME: {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    },
}

# https://docs.djangoproject.com/en/4.2/topics/i18n/
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_I18N = True
USE_TZ = False

LANGUAGES = [("pl", "Polski"), ("en", "English")]

# We're using Whitenoise - don't make this configurable.
# https://docs.djangoproject.com/en/4.2/howto/static-files/
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
