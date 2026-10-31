import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0002_auditlog"),
        ("catalog", "0002_paymentterm"),
        ("plans", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionNumberSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_value", models.PositiveBigIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name="QuotationTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("validity_days", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quotation_templates", to="plans.plan")),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("name", ""), _negated=True), name="subs_template_name_set"),
                    models.CheckConstraint(condition=models.Q(("validity_days__gte", 1)), name="subs_template_validity_gte_1"),
                ],
            },
        ),
        migrations.CreateModel(
            name="QuotationTemplateLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("is_addon", models.BooleanField(default=False)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="catalog.product")),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="subscriptions.quotationtemplate")),
                ("variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="catalog.productvariant")),
            ],
            options={
                "ordering": ["id"],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("quantity__gte", 1)), name="subs_template_line_quantity_gte_1"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(max_length=20, unique=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("quotation", "Quotation"), ("confirmed", "Confirmed"), ("active", "Active"), ("paused", "Paused"), ("closed", "Closed")], default="draft", max_length=16)),
                ("closed_reason", models.CharField(blank=True, choices=[("expired", "Quotation expired"), ("cancelled", "Cancelled"), ("plan_ended", "Plan ended")], max_length=16)),
                ("start_date", models.DateField()),
                ("expiry_date", models.DateField()),
                ("quotation_validity_days", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("valid_until", models.DateField(blank=True, null=True)),
                ("next_billing_date", models.DateField(blank=True, null=True)),
                ("payment_failed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="accounts.customer")),
                ("payment_terms", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="catalog.paymentterm")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="plans.plan")),
            ],
            options={
                "indexes": [models.Index(fields=["status"], name="subs_subscription_status_idx")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("status__in", ["draft", "quotation", "confirmed", "active", "paused", "closed"])), name="subs_subscription_status_valid"),
                    models.CheckConstraint(condition=models.Q(("expiry_date__gte", models.F("start_date"))), name="subs_subscription_dates_ordered"),
                    models.CheckConstraint(condition=models.Q(("quotation_validity_days__gte", 1)), name="subs_subscription_validity_gte_1"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SubscriptionLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("tax_rate", models.DecimalField(decimal_places=2, max_digits=5)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("tax_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("is_addon", models.BooleanField(default=False)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="catalog.product")),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="subscriptions.subscription")),
                ("variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="catalog.productvariant")),
            ],
            options={
                "ordering": ["id"],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("quantity__gte", 1)), name="subs_line_quantity_gte_1"),
                    models.CheckConstraint(condition=models.Q(("unit_price__gte", 0)), name="subs_line_unit_price_gte_0"),
                ],
            },
        ),
    ]
