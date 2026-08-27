import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("CONTROL_PANEL_DEBUG", "") == "1"

_secret_key_env = os.environ.get("CONTROL_PANEL_SECRET_KEY")
if not _secret_key_env and not DEBUG:
    raise RuntimeError(
        "CONTROL_PANEL_SECRET_KEY must be set - see docker-compose.yml's control-panel environment block"
    )
SECRET_KEY = _secret_key_env or "dev-only-insecure-key-do-not-deploy"

# Narrowed to match VerifySameOriginMiddleware's actual allowlist — not ["*"]
# anymore. Includes the nip.io hostname Traefik routes the panel on
# (panel.HOST_IP.nip.io): without it, proxied HTTPS requests return 400. Falls
# back to localhost-only in dev (HOST_IP unset) so "manage.py runserver" works.
_host_ip = os.environ.get("HOST_IP")
ALLOWED_HOSTS = [
    h
    for h in (_host_ip, "localhost", "127.0.0.1", "[::1]")
    if h
]
if _host_ip:
    ALLOWED_HOSTS.append(f"panel.{_host_ip}.nip.io")  # also enforced in core.middleware

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "auth_app",
    "cleanuparr",
    "nzbdav",
    "host_actions",
    "catalog",
    "watchstate",
    "queue_app",
    "host",
    "ui",
    "cli",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.VerifySameOriginMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("CONTROL_PANEL_DB_PATH", str(BASE_DIR / "dev-control-panel.db")),
    }
}

# django.contrib.auth's own User model (auth_user table, brand new — does not
# collide with the preserved `users` table) backs ONLY /admin/ logins via
# `manage.py createsuperuser`. The real control-panel login (auth_app) uses
# core.models.User against the preserved `users` table and never touches
# django.contrib.auth's session/user machinery — see core/authentication.py.

SESSION_COOKIE_NAME = "cp_session"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 days, matches the retired itsdangerous SESSION_MAX_AGE
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# ---------------------------------------------------------------------------
# Transport & cookie security (parent for improvement items 12/13)
# ---------------------------------------------------------------------------
# Wired to CONTROL_PANEL_SECURE_COOKIE (compose + .env). When truthy, session and
# CSRF cookies are TLS-only. Because this panel touches the Docker socket, secure
# is enabled by default; the tradeoff is that direct plain-HTTP access to :8420
# can no longer hold a session — use the Traefik HTTPS route (panel.HOST_IP.nip.io).
_secure_cookie = os.environ.get("CONTROL_PANEL_SECURE_COOKIE", "") == "1"

SESSION_COOKIE_SECURE = _secure_cookie
CSRF_COOKIE_SECURE = _secure_cookie

if not DEBUG:
    # HSTS: 1 year, include subdomains. Only meaningful over the HTTPS route;
    # Traefik already does the 80->443 redirect at the edge, so there is no
    # in-app SECURE_SSL_REDIRECT (it would loop against the TLS terminator).
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    # Defense-in-depth header hardening via SecurityMiddleware.
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    # Disallow <frame>/<iframe>/<embed> embedding so the panel can't be framed.
    X_FRAME_OPTIONS = "DENY"

    # POSTs through Traefik carry Origin https://panel.HOST_IP.nip.io; Django's
    # CSRF / our VerifySameOriginMiddleware compare against this list.
    CSRF_TRUSTED_ORIGINS = [f"https://panel.{_host_ip}.nip.io"] if _host_ip else []

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.authentication.SessionOrApiKeyAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["core.permissions.IsAuthenticatedOrServiceKey"],
    "EXCEPTION_HANDLER": "core.api_base.envelope_exception_handler",
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

LOGIN_URL = "auth_app:login"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Whitenoise serves collected static files in production (DEBUG=False)
# without needing nginx or a separate static file server.
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
