SECRET_KEY = "test-only-secret-key"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "railway_autoscaler",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
