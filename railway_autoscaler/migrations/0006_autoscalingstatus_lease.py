from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("railway_autoscaler", "0005_autoscalingpolicy_high_samples_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="autoscalingstatus",
            name="lease_owner",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="autoscalingstatus",
            name="lease_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="autoscalingstatus",
            name="state_version",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
