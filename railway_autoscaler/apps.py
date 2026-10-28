from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RailwayAutoscalerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "railway_autoscaler"
    verbose_name = _("Railway Autoscaler")
