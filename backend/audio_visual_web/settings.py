"""Django settings for the audio_visual_web project.

This backend powers the Audio Inspect web-app: it ingests audio dataset CSV
files, computes acoustic quality metrics, and serves analysis/export endpoints
to the React front-end. The configuration here is tuned for single-machine
local usage (the target user is a researcher/data engineer running it locally).
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY: local single-machine usage only. Do not deploy as-is to production.
SECRET_KEY = "django-insecure-audio-visual-web-local-dev-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "audio_visual_web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "audio_visual_web.wsgi.application"

# No relational DB is required: dataset state lives in the in-memory
# SessionStore. A throwaway sqlite db keeps Django happy if ever needed.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
}

# Allow the Vite dev server to call the API during local development.
CORS_ALLOW_ALL_ORIGINS = True

# Directory used for generated exports (filtered CSV / PDF reports).
WORKSPACE_DIR = BASE_DIR / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)

# Upper bound on number of audio files processed in one compute call. Guards
# against accidentally launching a multi-hour job from the UI.
MAX_AUDIO_FILES = 100000
