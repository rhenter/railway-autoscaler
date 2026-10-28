from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("railway_autoscaler", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="railwaycredential",
            name="credentials_token_f_8a4b0b_idx",
        ),
        migrations.RemoveField(
            model_name="railwaycredential",
            name="token_fingerprint",
        ),
    ]
