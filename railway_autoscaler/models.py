from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .fields import EncryptedTokenField


class RailwayCredential(models.Model):
    class TokenType(models.TextChoices):
        PROJECT = "project", _("Project")
        WORKSPACE = "workspace", _("Workspace")
        ACCOUNT = "account", _("Account")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="railway_credentials",
    )
    name = models.CharField(max_length=100)
    token = EncryptedTokenField(db_column="token_ciphertext")
    token_type = models.CharField(max_length=20, choices=TokenType.choices)
    project_id = models.CharField(max_length=100, blank=True)
    environment_id = models.CharField(max_length=100, blank=True)
    key_version = models.PositiveIntegerField(default=1, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("owner", "is_active")),
        ]
        verbose_name = _("Railway credential")
        verbose_name_plural = _("Railway credentials")

    def __str__(self) -> str:
        return f"{self.name} ({self.get_token_type_display()})"


class AutoscalingTarget(models.Model):
    class AgentType(models.TextChoices):
        HTTP = "http", _("HTTP")
        MESSAGE = "message", _("Message queue")
        RESOURCE = "resource", _("Resource advisor")

    credential = models.ForeignKey(
        RailwayCredential,
        on_delete=models.CASCADE,
        related_name="targets",
    )
    name = models.CharField(max_length=100)
    project_id = models.CharField(max_length=100)
    environment_id = models.CharField(max_length=100)
    service_id = models.CharField(max_length=100)
    service_name = models.CharField(max_length=100)
    agent_type = models.CharField(max_length=20, choices=AgentType.choices)
    queue_name = models.CharField(max_length=200, blank=True)
    enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("credential", "environment_id", "service_id"),
                name="unique_railway_target_per_environment",
            ),
        ]
        indexes = [
            models.Index(fields=("enabled", "agent_type")),
            models.Index(fields=("service_id", "environment_id")),
        ]
        verbose_name = _("Autoscaling target")
        verbose_name_plural = _("Autoscaling targets")

    def __str__(self) -> str:
        return f"{self.name} ({self.service_name})"


class AutoscalingPolicy(models.Model):
    target = models.OneToOneField(
        AutoscalingTarget,
        on_delete=models.CASCADE,
        related_name="policy",
    )
    target_per_replica = models.PositiveIntegerField(default=10)
    min_replicas = models.PositiveIntegerField(default=1)
    max_replicas = models.PositiveIntegerField(default=1)
    lower_threshold = models.FloatField(default=0.3)
    upper_threshold = models.FloatField(default=0.8)
    high_samples = models.PositiveIntegerField(default=3)
    low_samples = models.PositiveIntegerField(default=5)
    cooldown_seconds = models.PositiveIntegerField(default=60)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Autoscaling policy")
        verbose_name_plural = _("Autoscaling policies")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_replicas__gte=1),
                name="policy_min_replicas_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(max_replicas__gte=1),
                name="policy_max_replicas_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(min_replicas__lte=models.F("max_replicas")),
                name="policy_min_replicas_lte_max",
            ),
            models.CheckConstraint(
                condition=models.Q(lower_threshold__gte=0)
                & models.Q(lower_threshold__lt=models.F("upper_threshold"))
                & models.Q(upper_threshold__lte=1),
                name="policy_thresholds_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(high_samples__gte=1) & models.Q(low_samples__gte=1),
                name="policy_sample_windows_positive",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if self.min_replicas > self.max_replicas:
            raise ValidationError({"max_replicas": _("must be greater than or equal to minimum")})
        if not 0 <= self.lower_threshold < self.upper_threshold <= 1:
            raise ValidationError("thresholds must satisfy 0 <= lower < upper <= 1")
        if self.high_samples < 1 or self.low_samples < 1:
            raise ValidationError("sample windows must be positive")

    def __str__(self) -> str:
        return f"Policy for {self.target}"


class AutoscalingStatus(models.Model):
    class Health(models.TextChoices):
        UNKNOWN = "unknown", _("Unknown")
        HEALTHY = "healthy", _("Healthy")
        PAUSED = "paused", _("Paused")
        ERROR = "error", _("Error")

    target = models.OneToOneField(
        AutoscalingTarget,
        on_delete=models.CASCADE,
        related_name="status",
    )
    observed_replicas = models.PositiveIntegerField(null=True, blank=True)
    desired_replicas = models.PositiveIntegerField(null=True, blank=True)
    min_replicas = models.PositiveIntegerField(null=True, blank=True)
    max_replicas = models.PositiveIntegerField(null=True, blank=True)
    cpu_utilization = models.FloatField(null=True, blank=True)
    memory_utilization = models.FloatField(null=True, blank=True)
    sample_at = models.DateTimeField(null=True, blank=True)
    consecutive_high_samples = models.PositiveIntegerField(default=0)
    consecutive_low_samples = models.PositiveIntegerField(default=0)
    last_scaled_at = models.DateTimeField(null=True, blank=True)
    cooldown_until = models.DateTimeField(null=True, blank=True)
    pending_replicas = models.PositiveIntegerField(null=True, blank=True)
    run_id = models.CharField(max_length=100, blank=True)
    lease_owner = models.CharField(max_length=100, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    state_version = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    health = models.CharField(max_length=20, choices=Health.choices, default=Health.UNKNOWN)
    error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Autoscaling status")
        verbose_name_plural = _("Autoscaling statuses")

    def __str__(self) -> str:
        return f"Status for {self.target}"


class ScalingEvent(models.Model):
    class Outcome(models.TextChoices):
        PREVIEW = "preview", _("Preview")
        REQUESTED = "requested", _("Requested")
        CONFIRMED = "confirmed", _("Confirmed")
        FAILED = "failed", _("Failed")
        PAUSED = "paused", _("Paused")

    target = models.ForeignKey(
        AutoscalingTarget,
        on_delete=models.CASCADE,
        related_name="events",
    )
    run_id = models.CharField(max_length=100)
    reason = models.CharField(max_length=100)
    previous_replicas = models.PositiveIntegerField(null=True, blank=True)
    desired_replicas = models.PositiveIntegerField()
    confirmed_replicas = models.PositiveIntegerField(null=True, blank=True)
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("target", "created_at")),
            models.Index(fields=("run_id",)),
        ]
        verbose_name = _("Scaling event")
        verbose_name_plural = _("Scaling events")

    def __str__(self) -> str:
        return f"{self.target} -> {self.desired_replicas} ({self.outcome})"
