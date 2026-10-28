from django import forms
from django.conf import settings
from django.contrib import admin

from .client.exceptions import RailwayClientError
from .client.railway import RailwayGraphQLClient
from .models import (
    AutoscalingPolicy,
    AutoscalingStatus,
    AutoscalingTarget,
    RailwayCredential,
    ScalingEvent,
)


class RailwayCredentialAdminForm(forms.ModelForm):
    class Meta:
        model = RailwayCredential
        fields = ("owner", "name", "token", "token_type", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["token"].widget = forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        )
        self.fields.pop("project_id", None)
        self.fields.pop("environment_id", None)
        if self.instance.pk:
            self.fields["token"].required = False

    def clean_token(self):
        token = self.cleaned_data.get("token")
        if not token and self.instance.pk:
            return self.instance.token
        return token

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("token_type") == RailwayCredential.TokenType.PROJECT:
            token = cleaned_data.get("token")
            if token:
                try:
                    scope = RailwayGraphQLClient(
                        token,
                        use_project_token=True,
                        timeout=getattr(settings, "RAILWAY_AUTOSCALER_API_TIMEOUT", 20),
                    ).get_project_token_scope()
                except RailwayClientError as error:
                    raise forms.ValidationError(
                        "Could not discover the project from this token."
                    ) from error
                self.instance.project_id = scope.project_id
        return cleaned_data


@admin.register(RailwayCredential)
class RailwayCredentialAdmin(admin.ModelAdmin):
    form = RailwayCredentialAdminForm
    exclude = ("project_id", "environment_id")
    list_display = (
        "name",
        "owner",
        "token_type",
        "is_active",
        "created_at",
        "last_used_at",
    )
    list_filter = ("token_type", "is_active")
    search_fields = ("name",)
    readonly_fields = (
        "key_version",
        "created_at",
        "updated_at",
        "last_used_at",
    )


class AutoscalingPolicyInline(admin.StackedInline):
    model = AutoscalingPolicy
    extra = 0
    max_num = 1


@admin.register(AutoscalingTarget)
class AutoscalingTargetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "service_name",
        "agent_type",
        "credential",
        "enabled",
        "policy_min_replicas",
        "policy_max_replicas",
    )
    list_filter = ("agent_type", "enabled")
    search_fields = ("name", "service_name", "service_id", "environment_id")
    autocomplete_fields = ("credential",)
    list_select_related = ("credential", "policy")
    inlines = (AutoscalingPolicyInline,)

    @admin.display(description="Min replicas")
    def policy_min_replicas(self, obj):
        return getattr(getattr(obj, "policy", None), "min_replicas", "-")

    @admin.display(description="Max replicas")
    def policy_max_replicas(self, obj):
        return getattr(getattr(obj, "policy", None), "max_replicas", "-")


@admin.register(AutoscalingPolicy)
class AutoscalingPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "target",
        "min_replicas",
        "max_replicas",
        "target_per_replica",
        "cooldown_seconds",
        "updated_at",
    )
    search_fields = ("target__name", "target__service_name")
    autocomplete_fields = ("target",)


@admin.register(AutoscalingStatus)
class AutoscalingStatusAdmin(admin.ModelAdmin):
    list_display = (
        "target",
        "health",
        "observed_replicas",
        "desired_replicas",
        "sample_at",
        "updated_at",
    )
    list_filter = ("health",)
    search_fields = ("target__name", "target__service_name", "run_id")
    autocomplete_fields = ("target",)
    readonly_fields = [field.name for field in AutoscalingStatus._meta.fields]


@admin.register(ScalingEvent)
class ScalingEventAdmin(admin.ModelAdmin):
    list_display = (
        "target",
        "reason",
        "previous_replicas",
        "desired_replicas",
        "confirmed_replicas",
        "outcome",
        "created_at",
    )
    list_filter = ("outcome", "reason")
    search_fields = ("target__name", "target__service_name", "run_id")
    autocomplete_fields = ("target",)
    readonly_fields = [field.name for field in ScalingEvent._meta.fields]
