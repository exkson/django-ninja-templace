"""Django settings.

Every value is read from a plain environment variable via ``os.getenv`` —
this is the only module in the project allowed to read the environment.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Display name used in outgoing notifications (email subjects, OTP bodies).
APP_NAME = os.getenv("APP_NAME", "My App")

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-only-CHANGE-ME")
DEBUG = os.getenv("DEBUG", "true") == "true"
if allowed_hosts := os.getenv("ALLOWED_HOSTS"):
    ALLOWED_HOSTS = allowed_hosts.split(",")

if cors_allowed_origins := os.getenv("CORS_ALLOWED_ORIGINS"):
    CORS_ALLOWED_ORIGINS = [
        origin.strip() for origin in cors_allowed_origins.split(",") if origin.strip()
    ]

if csrf_trusted_origins := os.getenv("CSRF_TRUSTED_ORIGINS"):
    CSRF_TRUSTED_ORIGINS = [
        origin.strip() for origin in csrf_trusted_origins.split(",") if origin.strip()
    ]

INSTALLED_APPS = [
    "core.apps.CoreConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "templated_email",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.JWTAuthMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR.joinpath("core", "templates", "templated_email")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DATABASES: dict = {}
database_backend = os.getenv("DATABASE_BACKEND", "sqlite")
if database_backend == "sqlite":
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
elif database_backend == "postgres":
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DATABASE_NAME"),
        "USER": os.getenv("DATABASE_USER"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD"),
        "HOST": os.getenv("DATABASE_HOST", "localhost"),
        "PORT": os.getenv("DATABASE_PORT", "5432"),
    }
else:
    raise ValueError(f"Unsupported database backend: {database_backend}")


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "core.User"

# email is conditionally-unique via a non-empty UniqueConstraint, so USERNAME_FIELD
# isn't marked unique=True on the field itself. We enforce uniqueness via the
# UniqueConstraint on core.User. auth.E003 is the check that would fire
# otherwise — silencing it is deliberate; see core.models.user.User.Meta.
SILENCED_SYSTEM_CHECKS = ["auth.E003"]


LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "en-us")
LANGUAGES = [("en", "English"), ("fr", "Français")]
LOCALE_PATHS = [BASE_DIR / "core" / "locale"]
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Auth / JWT ---
# JWT_SECRET_KEY must be set in prod; an empty string produces unusable
# tokens (good — makes misconfiguration visible).
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
ACCESS_TOKEN_DURATION_MINUTES = int(os.getenv("ACCESS_TOKEN_DURATION_MINUTES", "15"))
REFRESH_TOKEN_DURATION_DAYS = int(os.getenv("REFRESH_TOKEN_DURATION_DAYS", "7"))

# Path prefixes served without a Bearer token. Everything else requires one.
JWT_PUBLIC_PATH_PREFIXES = [
    "/api/auth",
    "/api/docs",
    "/api/openapi.json",
    "/admin/",
    "/static/",
    "/media/",
]

# --- Email ---
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com")

# --- WhatsApp client (dotted path to class exposing `async def send`) ---
WHATSAPP_BACKEND = os.getenv(
    "WHATSAPP_BACKEND",
    "core.services.whatsapp.ConsoleWhatsAppClient",
)

# --- IP → country geocoding (URL template with {ip} placeholder) ---
GEO_IP_PROVIDER_URL = os.getenv("GEO_IP_PROVIDER_URL", "https://ipapi.co/{ip}/country/")
# ISO 3166-1 alpha-2 code used when the lookup is skipped or fails.
DEFAULT_COUNTRY = os.getenv("DEFAULT_COUNTRY", "")

# --- Frontend ---
# Base URL of the client app. Used to build deep links sent in notifications.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")


# --- Logging ---
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "filters": {
        "below_error": {
            "()": "config.logging_filters.MaxLevelFilter",
            "level": "ERROR",
        },
    },
    "handlers": {
        "services_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "services.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
        },
        "web_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "web.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
        },
        "notifications_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "notifications.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
            "filters": ["below_error"],
        },
        "notifications_errors_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "notifications.errors.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
            "level": "ERROR",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "core.services.notifications": {
            "handlers": ["notifications_file", "notifications_errors_file"]
            + (["console"] if DEBUG else []),
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "core.services": {
            "handlers": ["services_file"] + (["console"] if DEBUG else []),
            "level": "DEBUG" if DEBUG else "INFO",
        },
        "web": {
            "handlers": ["web_file"] + (["console"] if DEBUG else []),
            "level": "DEBUG" if DEBUG else "INFO",
        },
    },
}
