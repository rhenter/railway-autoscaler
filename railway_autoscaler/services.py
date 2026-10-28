from __future__ import annotations

from django.utils import timezone

from .fields import CredentialEncryptionError
from .models import RailwayCredential


class CredentialService:
    def create(
        self,
        *,
        owner,
        name: str,
        token: str,
        token_type: str,
        project_id: str = "",
        environment_id: str = "",
    ) -> RailwayCredential:
        if token_type not in RailwayCredential.TokenType.values:
            raise ValueError("token_type is invalid")
        credential = RailwayCredential(
            owner=owner,
            name=name,
            token=token,
            token_type=token_type,
            project_id=project_id,
            environment_id=environment_id,
        )
        credential.save()
        return credential

    def reveal(self, credential: RailwayCredential) -> str:
        if not credential.is_active:
            raise CredentialEncryptionError("credential is inactive")
        RailwayCredential.objects.filter(pk=credential.pk).update(last_used_at=timezone.now())
        return credential.token
