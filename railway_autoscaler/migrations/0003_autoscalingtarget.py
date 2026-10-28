import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("railway_autoscaler", "0002_remove_token_fingerprint"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutoscalingTarget",
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
                ("project_id", models.CharField(max_length=100)),
                ("environment_id", models.CharField(max_length=100)),
                ("service_id", models.CharField(max_length=100)),
                ("service_name", models.CharField(max_length=100)),
                (
                    "agent_type",
                    models.CharField(
                        choices=[
                            ("http", "HTTP"),
                            ("message", "Message queue"),
                            ("resource", "Resource advisor"),
                        ],
                        max_length=20,
                    ),
                ),
                ("queue_name", models.CharField(blank=True, max_length=200)),
                ("enabled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "credential",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="targets",
                        to="railway_autoscaler.railwaycredential",
                    ),
                ),
            ],
            options={
                "ordering": ("name",),
                "verbose_name": "Autoscaling target",
                "verbose_name_plural": "Autoscaling targets",
            },
        ),
        migrations.AddConstraint(
            model_name="autoscalingtarget",
            constraint=models.UniqueConstraint(
                fields=("credential", "environment_id", "service_id"),
                name="unique_railway_target_per_environment",
            ),
        ),
        migrations.AddIndex(
            model_name="autoscalingtarget",
            index=models.Index(
                fields=["enabled", "agent_type"], name="railway_aut_enabled_87e137_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="autoscalingtarget",
            index=models.Index(
                fields=["service_id", "environment_id"], name="railway_aut_service_d94c9c_idx"
            ),
        ),
        migrations.AlterModelOptions(
            name="railwaycredential",
            options={
                "ordering": ("-created_at",),
                "verbose_name": "Railway credential",
                "verbose_name_plural": "Railway credentials",
            },
        ),
        migrations.RenameIndex(
            model_name="railwaycredential",
            new_name="railway_aut_owner_i_9cd297_idx",
            old_name="credentials_owner_i_7d98d3_idx",
        ),
        migrations.CreateModel(
            name="AutoscalingPolicy",
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
                ("target_per_replica", models.PositiveIntegerField(default=10)),
                ("min_replicas", models.PositiveIntegerField(default=1)),
                ("max_replicas", models.PositiveIntegerField(default=1)),
                ("cooldown_seconds", models.PositiveIntegerField(default=60)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "target",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="policy",
                        to="railway_autoscaler.autoscalingtarget",
                    ),
                ),
            ],
            options={
                "verbose_name": "Autoscaling policy",
                "verbose_name_plural": "Autoscaling policies",
            },
        ),
        migrations.AddConstraint(
            model_name="autoscalingpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(min_replicas__gte=1),
                name="policy_min_replicas_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="autoscalingpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(max_replicas__gte=1),
                name="policy_max_replicas_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="autoscalingpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(min_replicas__lte=models.F("max_replicas")),
                name="policy_min_replicas_lte_max",
            ),
        ),
    ]
