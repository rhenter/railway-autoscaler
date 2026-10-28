from pathlib import Path

from dj_database_url import parse as parse_db_url
from prettyconf import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "test-secret-key"
USE_TZ = True
TIME_ZONE = "UTC"
ROOT_URLCONF = "test_django_project.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CELERY_TASK_LOGS_EXPIRES = 2
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "railway_autoscaler",
]

DATABASES = {"default": parse_db_url("sqlite:///db.sqlite3", engine="django.db.backends.sqlite3")}

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

RAILWAY_AUTOSCALER_DRY_RUN = True
RAILWAY_AUTOSCALER_API_TIMEOUT = 20
RAILWAY_AUTOSCALER_METRIC_WINDOW_SECONDS = 60

CELERY_BROKER_URL = "memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ROUTES = {"railway_autoscaler.reconcile": {"queue": "autoscaling"}}
# If the host uses django-celery-beat, create this same task in the PeriodicTask
# admin instead of duplicating it here in CELERY_BEAT_SCHEDULE.
CELERY_BEAT_SCHEDULE = {
    "evaluate-railway-autoscaling": {
        "task": "railway_autoscaler.reconcile",
        "schedule": 60.0,
        "options": {"queue": "autoscaling", "expires": 55},
    }
}

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "DIRS": [],
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

RAILWAY_AUTOSCALER_CREDENTIAL_KEY = config("RAILWAY_AUTOSCALER_CREDENTIAL_KEY")
