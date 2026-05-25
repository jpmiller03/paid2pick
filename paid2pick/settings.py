"""
Django settings for the Paid2Pick rebuild (Phase 1).

Dev defaults to SQLite and DEBUG on. Everything risky is env-overridable.
See REBUILD_PLAN.md (repo root) for the architecture this implements.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = (
    ["*"] if DEBUG
    else [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
)
# Render injects the public hostname automatically.
_paas_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if _paas_host:
    ALLOWED_HOSTS.append(_paas_host)
# CSRF needs the full https origin(s); behind Cloudflare/Render this is the public domain.
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in ("*", "")]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # project apps
    "accounts",
    "catalog",
    "picks",
    "contests",
    "wallet",
    "payments",
    "ingest",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serve static without a separate CDN origin
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "paid2pick.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "web.context_processors.wallet_balance",
            ],
        },
    },
]

WSGI_APPLICATION = "paid2pick.wsgi.application"

# Dev: SQLite (no env). Prod: set DATABASE_URL (e.g. a Neon Postgres URL).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
if os.environ.get("DATABASE_URL"):
    import dj_database_url
    DATABASES["default"] = dj_database_url.config(conn_max_age=600, ssl_require=True)

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
# The legacy app hard-coded America/Louisville; the picks listing shows EST.
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# WhiteNoise: compressed, hashed static files served straight from the app.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Production hardening (only when DEBUG is off). Behind the Render + Cloudflare proxies.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ---- Paid2Pick app config -------------------------------------------------
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_REGION = os.environ.get("ODDS_API_REGION", "us")
ODDS_API_MARKETS = "h2h,spreads,totals"

# Marketplace economics (Phase 1 = virtual coins; see MARKETPLACE_SPEC.md).
PICK_PRICE = int(os.environ.get("P2P_PICK_PRICE", "100"))   # coins
PLATFORM_CUT = float(os.environ.get("P2P_PLATFORM_CUT", "0.30"))
SIGNUP_GRANT = int(os.environ.get("P2P_SIGNUP_GRANT", "1000"))  # coins

# Picks lock / auto-reveal this many minutes before kickoff.
LOCK_LEAD_MINUTES = int(os.environ.get("P2P_LOCK_LEAD_MINUTES", "30"))

# Payments seam (Phase 4). "fake" = offline demo; "stripe" = real (behind keys + legal gate).
PAYMENTS_PROVIDER = os.environ.get("P2P_PAYMENTS_PROVIDER", "fake")
COINS_PER_CENT = int(os.environ.get("P2P_COINS_PER_CENT", "1"))  # 1 coin = 1 cent
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
