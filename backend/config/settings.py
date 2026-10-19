"""Django settings. Everything environment-specific comes from env vars."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "rest_framework",
    "corsheaders",
    "routing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = []

# No persistent data: routes are computed per request and weather is cached.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "trucks"}}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}

# CORS: set CORS_ALLOWED_ORIGINS="https://your-app.vercel.app" in production.
_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _origins:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]
else:
    CORS_ALLOW_ALL_ORIGINS = True

# --- External services -------------------------------------------------------
OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
OPEN_METEO_URL = os.environ.get("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
HTTP_USER_AGENT = os.environ.get("HTTP_USER_AGENT", "weather-aware-truck-routing/1.0 (take-home assessment)")

WEATHER_CACHE_SECONDS = 30 * 60
WEATHER_STALE_SECONDS = 12 * 3600  # last-known forecast, used only if a live refresh fails
GEOCODE_CACHE_SECONDS = 24 * 3600
# Multiplier on OSRM (car) durations to approximate a loaded truck. 1.0 = unchanged.
TRUCK_TIME_FACTOR = float(os.environ.get("TRUCK_TIME_FACTOR", "1.0"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
