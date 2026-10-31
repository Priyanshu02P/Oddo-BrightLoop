import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("action", models.CharField(max_length=64)),
                ("target_type", models.CharField(max_length=64)),
                ("target_id", models.PositiveBigIntegerField()),
                ("from_status", models.CharField(blank=True, max_length=16)),
                ("to_status", models.CharField(blank=True, max_length=16)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["target_type", "target_id", "created_at"],
                        name="accounts_audit_target_idx",
                    )
                ],
            },
        ),
    ]
