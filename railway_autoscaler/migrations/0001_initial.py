import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import railway_autoscaler.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RailwayCredential",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                (
                    "token",
                    railway_autoscaler.fields.EncryptedTokenField(db_column="token_ciphertext"),
                ),
                (
                    "token_type",
                    models.CharField(
                        choices=[
                            ("project", "Project"),
                            ("workspace", "Workspace"),
                            ("account", "Account"),
                        ],
                        max_length=20,
                    ),
                ),
                ("project_id", models.CharField(blank=True, max_length=100)),
                ("environment_id", models.CharField(blank=True, max_length=100)),
                ("token_fingerprint", models.CharField(editable=False, max_length=64)),
                ("key_version", models.PositiveIntegerField(default=1, editable=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="railway_credentials",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="railwaycredential",
            index=models.Index(
                fields=["owner", "is_active"], name="credentials_owner_i_7d98d3_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="railwaycredential",
            index=models.Index(fields=["token_fingerprint"], name="credentials_token_f_8a4b0b_idx"),
        ),
    ]
