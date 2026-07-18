"""
Django settings for RedlineGuard.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Decision memory embeddings: MiniLM by default (FAKE_EMBED=0).
# Offline/hash: set FAKE_EMBED=1. Tests default to hash unless you override.
_default_embed = "1" if "test" in sys.argv else "0"
os.environ.setdefault("FAKE_EMBED", os.environ.get("FAKE_EMBED", _default_embed))

SECRET_KEY = "django-insecure-wv)v^v5%#=dkr!u)6$bkb(l07(^x#r$oiej2r7+o&1sa3_zf3q"

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.contracts",
    "apps.security",
    "apps.review",
    "apps.learning.apps.LearningConfig",
    "apps.decisions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# RedlineGuard data roots
DATA_DIR = BASE_DIR / "data"
SCRATCH_CORPUS_DIR = DATA_DIR / "scratch_corpus"
MALICIOUS_CORPUS_DIR = DATA_DIR / "malicious_corpus"
PLAYBOOK_CORPUS_DIR = DATA_DIR / "playbook_corpus"
PLAYBOOK_PATH = DATA_DIR / "playbook_config.json"
PLAYBOOK_OVERRIDES_PATH = DATA_DIR / "playbook_overrides.json"
CHROMA_PATH = DATA_DIR / "vector_memory"
# v2 embeds clause excerpts (not playbook reason boilerplate). Wipe old collection or leave it.
CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "django_decisions_v2")
# Cosine distance gate: MiniLM ~0.45; hash embedder is looser (tests use hash).
_fake_embed = os.environ.get("FAKE_EMBED", "0").strip() not in ("0", "false", "False")
_default_max_dist = "0.85" if _fake_embed else "0.45"
MEMORY_MAX_DISTANCE = float(os.environ.get("MEMORY_MAX_DISTANCE", _default_max_dist))

# LLM draft port (Needs-human counters). Default Fake — no API key required.
FAKE_LLM = os.environ.get("FAKE_LLM", "1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
