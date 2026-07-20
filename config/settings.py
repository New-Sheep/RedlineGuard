"""
Django settings for RedlineGuard.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env if present (does not override existing process env)
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Decision memory embeddings: MiniLM by default (FAKE_EMBED=0).
# Offline/hash: set FAKE_EMBED=1. Tests default to hash unless you override.
_default_embed = "1" if "test" in sys.argv else "0"
os.environ.setdefault("FAKE_EMBED", os.environ.get("FAKE_EMBED", _default_embed))

# Force offline Fake LLM during `manage.py test` (ignore .env FAKE_LLM=0).
# Opt into live LLM in tests with TEST_LIVE_LLM=1.
if "test" in sys.argv and os.environ.get("TEST_LIVE_LLM", "").strip() not in (
    "1",
    "true",
    "True",
):
    os.environ["FAKE_LLM"] = "1"

SECRET_KEY = "django-insecure-wv)v^v5%#=dkr!u)6$bkb(l07(^x#r$oiej2r7+o&1sa3_zf3q"

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# Session auth for demos / pen-test. Tests default off so existing suite stays green.
_require_auth_env = os.environ.get("REQUIRE_AUTH")
if _require_auth_env is not None:
    REQUIRE_AUTH = _require_auth_env.strip() not in ("0", "false", "False", "")
elif "test" in sys.argv:
    REQUIRE_AUTH = False
else:
    REQUIRE_AUTH = True

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/contracts/"
LOGOUT_REDIRECT_URL = "/login/"

# Security headers (HSTS off locally — no HTTPS in take-home zip)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "SAMEORIGIN"  # allow same-origin PDF iframe on Review; still blocks foreign clickjacking
SECURE_REFERRER_POLICY = "same-origin"
# Report-only CSP for demo (does not break inline scripts in templates)
CONTENT_SECURITY_POLICY_REPORT_ONLY = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'"
)
CSRF_COOKIE_HTTPONLY = False  # allow JS to read for X-CSRFToken on JSON APIs
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts.apps.AccountsConfig",
    "apps.core",
    "apps.contracts",
    "apps.security",
    "apps.review",
    "apps.learning.apps.LearningConfig",
    "apps.decisions",
    "apps.drafting.apps.DraftingConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.accounts.security_headers.ExtraSecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.RequireAuthMiddleware",
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

# Layered playbook compare: L0 regex + L1 local semantic (no LLM judge this sprint)
SEMANTIC_COMPARE = os.environ.get("SEMANTIC_COMPARE", "1").strip() not in (
    "0",
    "false",
    "False",
    "",
)
SEMANTIC_MAX_DISTANCE = float(
    os.environ.get("SEMANTIC_MAX_DISTANCE", _default_max_dist)
)
_default_strict = "0.55" if _fake_embed else "0.35"
SEMANTIC_STRICT_DISTANCE = float(
    os.environ.get("SEMANTIC_STRICT_DISTANCE", _default_strict)
)

# LLM drafts for Needs-human counters. Default Fake — no Ollama/API required.
FAKE_LLM = os.environ.get("FAKE_LLM", "1")
# When FAKE_LLM=0: ollama | nvidia | deepseek | moonshot | http | auto
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "auto")
# Local Ollama (used when FAKE_LLM=0 and provider is ollama / auto with no cloud keys)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT_S", "120"))
# L2 closed-book judge after L0+L1.
# None / unset => auto: on when FAKE_LLM=0, off when Fake.
_llm_judge_env = os.environ.get("LLM_JUDGE")
if _llm_judge_env is None:
    LLM_JUDGE = None  # auto from FAKE_LLM at compare time
else:
    LLM_JUDGE = _llm_judge_env.strip() not in ("0", "false", "False", "")
LLM_JUDGE_MAX_FINDINGS = int(os.environ.get("LLM_JUDGE_MAX_FINDINGS", "8"))
# Magical-sprint agent toggles (empty = auto on when FAKE_LLM=0; Discover/GapSuggest default off)
LLM_PLAYBOOK_PROPOSE = os.environ.get("LLM_PLAYBOOK_PROPOSE", "")
LLM_REWRITE_COPILOT = os.environ.get("LLM_REWRITE_COPILOT", "")
LLM_MEMORY_EXPLAIN = os.environ.get("LLM_MEMORY_EXPLAIN", "")
LLM_DECISION_BRIEF = os.environ.get("LLM_DECISION_BRIEF", "")
LLM_MEMORY_ENRICH = os.environ.get("LLM_MEMORY_ENRICH", "")
LLM_PLAIN_ENGLISH = os.environ.get("LLM_PLAIN_ENGLISH", "")
LLM_SCOPED_ASK = os.environ.get("LLM_SCOPED_ASK", "")
LLM_GAP_SUGGEST = os.environ.get("LLM_GAP_SUGGEST", "0")
LLM_DISCOVER = os.environ.get("LLM_DISCOVER", "0")
LLM_SECURITY_ADJUDICATE = os.environ.get("LLM_SECURITY_ADJUDICATE", "")
LLM_CONTEXT_AGENT = os.environ.get("LLM_CONTEXT_AGENT", "")
# Generic OpenAI-compatible HTTP (LLM_PROVIDER=http) + optional per-provider keys
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
# Session-lite analyze rate limit (demable guard)
MAX_ANALYZES_PER_HOUR = int(os.environ.get("MAX_ANALYZES_PER_HOUR", "30"))
# Auth endpoint rate limit (login attempts per hour per session)
MAX_LOGIN_ATTEMPTS_PER_HOUR = int(os.environ.get("MAX_LOGIN_ATTEMPTS_PER_HOUR", "20"))

# Narrow ReAct draft agent (vision M8). Fake path always returns a canned trace.
REACT_DRAFT = os.environ.get("REACT_DRAFT", "1").strip() not in (
    "0",
    "false",
    "False",
    "",
)
REACT_DRAFT_MAX_ITERS = int(os.environ.get("REACT_DRAFT_MAX_ITERS", "6"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
