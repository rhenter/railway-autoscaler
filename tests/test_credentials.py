from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.forms import PasswordInput

from railway_autoscaler.admin import RailwayCredentialAdminForm
from railway_autoscaler.fields import CredentialEncryptionError
from railway_autoscaler.models import AutoscalingPolicy, AutoscalingTarget, RailwayCredential
from railway_autoscaler.services import CredentialService


@pytest.fixture
def encryption_key(settings):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    settings.RAILWAY_AUTOSCALER_CREDENTIAL_KEY = key
    return key


@pytest.mark.django_db
def test_invalid_key_fails_closed(settings):
    settings.RAILWAY_AUTOSCALER_CREDENTIAL_KEY = "invalid-key"
    owner = get_user_model().objects.create_user(username="operator")
    credential = RailwayCredential(
        owner=owner,
        name="production",
        token="railway-token",
        token_type=RailwayCredential.TokenType.PROJECT,
    )

    with pytest.raises(CredentialEncryptionError):
        credential.save()


@pytest.mark.django_db
def test_service_stores_encrypted_project_credential(encryption_key):
    owner = get_user_model().objects.create_user(username="operator")
    service = CredentialService()

    credential = service.create(
        owner=owner,
        name="production",
        token="railway-token",
        token_type=RailwayCredential.TokenType.PROJECT,
        project_id="project-id",
        environment_id="environment-id",
    )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT token_ciphertext FROM railway_autoscaler_railwaycredential WHERE id = %s",
            [credential.pk],
        )
        stored_value = cursor.fetchone()[0]

    assert stored_value != "railway-token"
    assert service.reveal(credential) == "railway-token"
    assert RailwayCredential.objects.get(pk=credential.pk).last_used_at is not None


@pytest.mark.django_db
def test_model_field_encrypts_before_save(encryption_key):
    owner = get_user_model().objects.create_user(username="operator")
    credential = RailwayCredential(
        owner=owner,
        name="production",
        token="railway-token",
        token_type=RailwayCredential.TokenType.PROJECT,
    )

    credential.save()

    assert credential.token == "railway-token"


def test_admin_form_exposes_token_as_password_input():
    form_field = RailwayCredential._meta.get_field("token").formfield()

    assert isinstance(form_field.widget, PasswordInput)
    assert form_field.widget.render_value is True


def test_admin_model_form_keeps_token_secret_and_uses_password_input():
    form = RailwayCredentialAdminForm()

    assert isinstance(form.fields["token"].widget, PasswordInput)
    assert form.fields["token"].widget.render_value is False
    assert "project_id" not in form.fields
    assert "environment_id" not in form.fields


@pytest.mark.django_db
def test_project_token_scope_is_discovered_instead_of_entered_manually(encryption_key):
    owner = get_user_model().objects.create_user(username="operator")
    form_data = {
        "owner": owner.pk,
        "name": "production",
        "token": "railway-token",
        "token_type": RailwayCredential.TokenType.PROJECT,
        "is_active": "on",
    }
    scope = SimpleNamespace(
        project_id="discovered-project", environment_id="discovered-environment"
    )

    with patch("railway_autoscaler.admin.RailwayGraphQLClient") as client_class:
        client_class.return_value.get_project_token_scope.return_value = scope
        form = RailwayCredentialAdminForm(data=form_data)

        assert form.is_valid(), form.errors
        credential = form.save(commit=False)

    assert credential.project_id == "discovered-project"
    assert credential.environment_id == ""
    client_class.return_value.get_project_token_scope.assert_called_once_with()


@pytest.mark.django_db
def test_autoscaling_target_starts_disabled_and_is_scoped_to_service(encryption_key):
    owner = get_user_model().objects.create_user(username="operator")
    credential = CredentialService().create(
        owner=owner,
        name="production",
        token="railway-token",
        token_type=RailwayCredential.TokenType.PROJECT,
    )

    target = AutoscalingTarget.objects.create(
        credential=credential,
        name="production api",
        project_id="project-id",
        environment_id="environment-id",
        service_id="service-id",
        service_name="api",
        agent_type=AutoscalingTarget.AgentType.HTTP,
    )

    assert target.enabled is False
    policy = AutoscalingPolicy.objects.create(target=target)

    assert policy.min_replicas == policy.max_replicas == 1
