import django
from django.conf import settings


def pytest_configure(config):
    if not settings.configured:
        settings.configure(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "rest_framework",
                "apps.transactions",
            ],
            REST_FRAMEWORK={
                "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
                "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
            },
            ROOT_URLCONF="config.urls",
            USE_TZ=True,
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            MIDDLEWARE=[
                "apps.transactions.middleware.ResponseTimeMiddleware",
                "django.middleware.common.CommonMiddleware",
            ],
            LOGGING={
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {
                    "console": {"class": "logging.StreamHandler"},
                },
                "loggers": {
                    "transactions.middleware": {
                        "handlers": ["console"],
                        "level": "INFO",
                        "propagate": True,
                    },
                },
            },
        )
