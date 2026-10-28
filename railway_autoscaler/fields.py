from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from django import forms
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class CredentialEncryptionError(RuntimeError):
    """The credential encryption key is missing or invalid."""


def _fernet() -> Fernet:
    key = getattr(settings, "RAILWAY_AUTOSCALER_CREDENTIAL_KEY", None)
    if not key:
        raise CredentialEncryptionError("RAILWAY_AUTOSCALER_CREDENTIAL_KEY must be configured")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (TypeError, ValueError) as error:
        raise CredentialEncryptionError("credential encryption key is invalid") from error


class EncryptedTokenField(models.TextField):
    description = _("Encrypted credential token")

    def formfield(self, **kwargs):
        defaults = {
            "form_class": forms.CharField,
            "widget": forms.PasswordInput(
                render_value=True,
                attrs={"autocomplete": "new-password"},
            ),
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def get_db_prep_save(self, value, connection, prepared=False):
        if value is not None and prepared is False:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("token must be a non-empty string")
            value = _fernet().encrypt(value.encode()).decode()
        return super().get_db_prep_save(value, connection)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        try:
            return _fernet().decrypt(value.encode()).decode()
        except (InvalidToken, UnicodeDecodeError) as error:
            raise CredentialEncryptionError("credential could not be decrypted") from error
