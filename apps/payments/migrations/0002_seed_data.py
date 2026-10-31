import datetime
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils import timezone


def seed_demo_data(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Customer = apps.get_model("accounts", "Customer")
    Tax = apps.get_model("catalog", "Tax")
    PaymentTerm = apps.get_model("catalog", "PaymentTerm")
    Product = apps.get_model("catalog", "Product")
    ProductVariant = apps.get_model("catalog", "ProductVariant")
    Plan = apps.get_model("plans", "Plan")
    QuotationTemplate = apps.get_model("subscriptions", "QuotationTemplate")
    QuotationTemplateLine = apps.get_model("subscriptions", "QuotationTemplateLine")
    SubscriptionNumberSequence = apps.get_model("subscriptions", "SubscriptionNumberSequence")
    Subscription = apps.get_model("subscriptions", "Subscription")
    SubscriptionLine = apps.get_model("subscriptions", "SubscriptionLine")
    InvoiceNumberSequence = apps.get_model("billing", "InvoiceNumberSequence")
    Invoice = apps.get_model("billing", "Invoice")
    InvoiceLine = apps.get_model("billing", "InvoiceLine")
    Discount = apps.get_model("discounts", "Discount")
    PaymentReferenceSequence = apps.get_model("payments", "PaymentReferenceSequence")
    Payment = apps.get_model("payments", "Payment")

    now = timezone.now()

    # 1. Users
    admin_user, _ = User.objects.get_or_create(
        email="admin@brightloop.com",
        defaults={
            "role": "admin",
            "is_active": True,
            "password": make_password("Admin#12345"),
            "date_joined": now,
        },
    )

    staff_user, _ = User.objects.get_or_create(
        email="staff@brightloop.com",
        defaults={
            "role": "staff",
            "is_active": True,
            "password": make_password("Staff#12345"),
            "date_joined": now,
        },
    )

    acme_user, _ = User.objects.get_or_create(
        email="acme.corp@example.com",
        defaults={
            "role": "customer",
            "is_active": True,
            "password": make_password("Customer#12345"),
            "date_joined": now,
        },
    )
    acme_customer, _ = Customer.objects.get_or_create(user=acme_user)

    globex_user, _ = User.objects.get_or_create(
        email="globex@example.com",
        defaults={
            "role": "customer",
            "is_active": True,
            "password": make_password("Customer#12345"),
            "date_joined": now,
        },
    )
    globex_customer, _ = Customer.objects.get_or_create(user=globex_user)

    stark_user, _ = User.objects.get_or_create(
        email="stark@example.com",
        defaults={
            "role": "customer",
            "is_active": True,
            "password": make_password("Customer#12345"),
            "date_joined": now,
        },
    )
    stark_customer, _ = Customer.objects.get_or_create(user=stark_user)

    # 2. Taxes
    vat_15, _ = Tax.objects.get_or_create(
        name="VAT (15%)",
        defaults={"rate": Decimal("15.00")},
    )
    gst_18, _ = Tax.objects.get_or_create(
        name="Standard GST (18%)",
        defaults={"rate": Decimal("18.00")},
    )
    reduced_5, _ = Tax.objects.get_or_create(
        name="Reduced Rate (5%)",
        defaults={"rate": Decimal("5.00")},
    )
    zero_tax, _ = Tax.objects.get_or_create(
        name="Zero Rate (0%)",
        defaults={"rate": Decimal("0.00")},
    )

    # 3. Payment Terms
    term_immediate, _ = PaymentTerm.objects.get_or_create(
        name="Immediate",
        defaults={"days": 0},
    )
    term_net15, _ = PaymentTerm.objects.get_or_create(
        name="Net 15",
        defaults={"days": 15},
    )
    term_net30, _ = PaymentTerm.objects.get_or_create(
        name="Net 30",
        defaults={"days": 30},
    )
    term_net60, _ = PaymentTerm.objects.get_or_create(
        name="Net 60",
        defaults={"days": 60},
    )

    # 4. Products & Variants
    prod_suite, _ = Product.objects.get_or_create(
        name="Brightloop Cloud Suite",
        defaults={
            "type": "service",
            "sales_price": Decimal("1500.00"),
            "cost_price": Decimal("600.00"),
            "notes": "Core recurring platform for business operations.",
            "tax": gst_18,
            "is_archived": False,
        },
    )
    ProductVariant.objects.get_or_create(
        product=prod_suite,
        dimension="Edition",
        value="Professional",
        defaults={"price_adjustment": Decimal("500.00")},
    )
    ProductVariant.objects.get_or_create(
        product=prod_suite,
        dimension="Edition",
        value="Enterprise",
        defaults={"price_adjustment": Decimal("1500.00")},
    )

    prod_acct, _ = Product.objects.get_or_create(
        name="Dedicated Account Manager",
        defaults={
            "type": "service",
            "sales_price": Decimal("800.00"),
            "cost_price": Decimal("300.00"),
            "notes": "Personalized technical and business advisory services.",
            "tax": vat_15,
            "is_archived": False,
        },
    )

    prod_token, _ = Product.objects.get_or_create(
        name="Security Hardware Token",
        defaults={
            "type": "goods",
            "sales_price": Decimal("75.00"),
            "cost_price": Decimal("30.00"),
            "notes": "FIDO2 WebAuthn cryptographic key.",
            "tax": vat_15,
            "is_archived": False,
        },
    )

    prod_sla, _ = Product.objects.get_or_create(
        name="24/7 SLA Premium Support",
        defaults={
            "type": "service",
            "sales_price": Decimal("450.00"),
            "cost_price": Decimal("150.00"),
            "notes": "Priority 1-hour critical response SLA add-on.",
            "tax": gst_18,
            "is_archived": False,
        },
    )

    # 5. Plans
    plan_starter, _ = Plan.objects.get_or_create(
        name="Starter Monthly",
        defaults={
            "price": Decimal("499.00"),
            "billing_period": "monthly",
            "minimum_quantity": 1,
            "availability_start_date": datetime.date(2026, 1, 1),
            "availability_end_date": datetime.date(2030, 12, 31),
            "renewal_mode": "automatic",
            "auto_close_at_end_date": False,
            "allow_close_early": True,
            "allow_pause": True,
            "allow_renew": True,
        },
    )

    plan_pro, _ = Plan.objects.get_or_create(
        name="Professional Monthly",
        defaults={
            "price": Decimal("1499.00"),
            "billing_period": "monthly",
            "minimum_quantity": 1,
            "availability_start_date": datetime.date(2026, 1, 1),
            "availability_end_date": datetime.date(2030, 12, 31),
            "renewal_mode": "automatic",
            "auto_close_at_end_date": False,
            "allow_close_early": True,
            "allow_pause": True,
            "allow_renew": True,
        },
    )

    plan_ent, _ = Plan.objects.get_or_create(
        name="Enterprise Annual",
        defaults={
            "price": Decimal("14999.00"),
            "billing_period": "yearly",
            "minimum_quantity": 1,
            "availability_start_date": datetime.date(2026, 1, 1),
            "availability_end_date": datetime.date(2030, 12, 31),
            "renewal_mode": "automatic",
            "auto_close_at_end_date": False,
            "allow_close_early": True,
            "allow_pause": True,
            "allow_renew": True,
        },
    )

    # 6. Quotation Templates
    template, _ = QuotationTemplate.objects.get_or_create(
        name="Standard SaaS Onboarding",
        defaults={
            "plan": plan_pro,
            "validity_days": 30,
        },
    )
    QuotationTemplateLine.objects.get_or_create(
        template=template,
        product=prod_suite,
        defaults={"quantity": 1, "is_addon": False},
    )
    QuotationTemplateLine.objects.get_or_create(
        template=template,
        product=prod_sla,
        defaults={"quantity": 1, "is_addon": True},
    )

    # 7. Discounts
    Discount.objects.get_or_create(
        name="Spring Welcome Promo",
        defaults={
            "discount_type": "fixed",
            "value": Decimal("100.00"),
            "minimum_purchase_amount": Decimal("500.00"),
            "minimum_quantity": 1,
            "start_date": datetime.date(2026, 1, 1),
            "end_date": datetime.date(2030, 12, 31),
            "usage_limit_per_customer": 2,
            "scope_type": "whole_subscription",
            "is_active": True,
            "created_by": admin_user,
        },
    )
    Discount.objects.get_or_create(
        name="Enterprise 10% Partner Discount",
        defaults={
            "discount_type": "percentage",
            "value": Decimal("10.00"),
            "start_date": datetime.date(2026, 1, 1),
            "end_date": datetime.date(2030, 12, 31),
            "usage_limit_per_customer": 5,
            "scope_type": "whole_subscription",
            "is_active": True,
            "created_by": admin_user,
        },
    )

    # 8. Sequences
    sub_seq, _ = SubscriptionNumberSequence.objects.get_or_create(pk=1)
    if sub_seq.last_value < 3:
        sub_seq.last_value = 3
        sub_seq.save()

    inv_seq, _ = InvoiceNumberSequence.objects.get_or_create(pk=1)
    if inv_seq.last_value < 3:
        inv_seq.last_value = 3
        inv_seq.save()

    pay_seq, _ = PaymentReferenceSequence.objects.get_or_create(pk=1)
    if pay_seq.last_value < 1:
        pay_seq.last_value = 1
        pay_seq.save()

    # 9. Subscriptions
    sub_1, _ = Subscription.objects.get_or_create(
        number="SUB-000001",
        defaults={
            "customer": acme_customer,
            "plan": plan_pro,
            "payment_terms": term_net30,
            "status": "active",
            "start_date": datetime.date(2026, 9, 1),
            "expiry_date": datetime.date(2027, 8, 31),
            "quotation_validity_days": 30,
            "next_billing_date": datetime.date(2026, 11, 1),
        },
    )
    if not sub_1.lines.exists():
        SubscriptionLine.objects.create(
            subscription=sub_1,
            product=prod_suite,
            quantity=1,
            unit_price=Decimal("1500.00"),
            tax_rate=Decimal("18.00"),
            amount=Decimal("1500.00"),
            tax_amount=Decimal("270.00"),
            is_addon=False,
        )
        SubscriptionLine.objects.create(
            subscription=sub_1,
            product=prod_sla,
            quantity=1,
            unit_price=Decimal("450.00"),
            tax_rate=Decimal("18.00"),
            amount=Decimal("450.00"),
            tax_amount=Decimal("81.00"),
            is_addon=True,
        )

    sub_2, _ = Subscription.objects.get_or_create(
        number="SUB-000002",
        defaults={
            "customer": globex_customer,
            "plan": plan_ent,
            "payment_terms": term_net15,
            "status": "active",
            "start_date": datetime.date(2026, 9, 15),
            "expiry_date": datetime.date(2027, 9, 14),
            "quotation_validity_days": 15,
            "next_billing_date": datetime.date(2026, 10, 15),
        },
    )
    if not sub_2.lines.exists():
        SubscriptionLine.objects.create(
            subscription=sub_2,
            product=prod_suite,
            quantity=2,
            unit_price=Decimal("1500.00"),
            tax_rate=Decimal("18.00"),
            amount=Decimal("3000.00"),
            tax_amount=Decimal("540.00"),
            is_addon=False,
        )
        SubscriptionLine.objects.create(
            subscription=sub_2,
            product=prod_acct,
            quantity=1,
            unit_price=Decimal("800.00"),
            tax_rate=Decimal("15.00"),
            amount=Decimal("800.00"),
            tax_amount=Decimal("120.00"),
            is_addon=True,
        )

    sub_3, _ = Subscription.objects.get_or_create(
        number="SUB-000003",
        defaults={
            "customer": stark_customer,
            "plan": plan_starter,
            "payment_terms": term_immediate,
            "status": "quotation",
            "start_date": datetime.date(2026, 11, 1),
            "expiry_date": datetime.date(2027, 10, 31),
            "quotation_validity_days": 30,
            "valid_until": datetime.date(2026, 11, 30),
        },
    )
    if not sub_3.lines.exists():
        SubscriptionLine.objects.create(
            subscription=sub_3,
            product=prod_suite,
            quantity=1,
            unit_price=Decimal("1500.00"),
            tax_rate=Decimal("18.00"),
            amount=Decimal("1500.00"),
            tax_amount=Decimal("270.00"),
            is_addon=False,
        )

    # 10. Invoices
    inv_1 = Invoice.objects.filter(number="INV-000001").first()
    if not inv_1:
        inv_1 = Invoice.objects.create(
            number="INV-000001",
            subscription=sub_1,
            customer=acme_customer,
            customer_email="acme.corp@example.com",
            plan_name="Professional Monthly",
            payment_terms_name="Net 30",
            period_start=datetime.date(2026, 9, 1),
            period_end=datetime.date(2026, 9, 30),
            invoice_date=datetime.date(2026, 9, 1),
            due_date=datetime.date(2026, 10, 1),
            untaxed_amount=Decimal("1950.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("351.00"),
            total=Decimal("2301.00"),
            status="draft",
        )
        InvoiceLine.objects.create(
            invoice=inv_1,
            product=prod_suite,
            description="Brightloop Cloud Suite",
            quantity=1,
            unit_price=Decimal("1500.00"),
            tax_rate=Decimal("18.00"),
            amount=Decimal("1500.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("270.00"),
            is_addon=False,
        )
        InvoiceLine.objects.create(
            invoice=inv_1,
            product=prod_sla,
            description="24/7 SLA Premium Support",
            quantity=1,
            unit_price=Decimal("450.00"),
            tax_rate=Decimal("18.00"),
            amount=Decimal("450.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("81.00"),
            is_addon=True,
        )
        inv_1.status = "paid"
        inv_1.confirmed_at = now
        inv_1.paid_at = now
        inv_1.save(update_fields=["status", "confirmed_at", "paid_at"])

    inv_2 = Invoice.objects.filter(number="INV-000002").first()
    if not inv_2:
        inv_2 = Invoice.objects.create(
            number="INV-000002",
            subscription=sub_1,
            customer=acme_customer,
            customer_email="acme.corp@example.com",
            plan_name="Professional Monthly",
            payment_terms_name="Net 30",
            period_start=datetime.date(2026, 10, 1),
            period_end=datetime.date(2026, 10, 31),
            invoice_date=datetime.date(2026, 10, 1),
            due_date=datetime.date(2026, 10, 31),
            untaxed_amount=Decimal("1950.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("351.00"),
            total=Decimal("2301.00"),
            status="draft",
        )
        InvoiceLine.objects.create(
            invoice=inv_2,
            product=prod_suite,
            description="Brightloop Cloud Suite",
            quantity=1,
            unit_price=Decimal("1500.00"),
            tax_rate=Decimal("18.00"),
            amount=Decimal("1500.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("270.00"),
            is_addon=False,
        )
        InvoiceLine.objects.create(
            invoice=inv_2,
            product=prod_sla,
            description="24/7 SLA Premium Support",
            quantity=1,
            unit_price=Decimal("450.00"),
            tax_rate=Decimal("18.00"),
            amount=Decimal("450.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("81.00"),
            is_addon=True,
        )
        inv_2.status = "confirmed"
        inv_2.confirmed_at = now
        inv_2.save(update_fields=["status", "confirmed_at"])

    inv_3 = Invoice.objects.filter(number="INV-000003").first()
    if not inv_3:
        inv_3 = Invoice.objects.create(
            number="INV-000003",
            subscription=sub_2,
            customer=globex_customer,
            customer_email="globex@example.com",
            plan_name="Enterprise Annual",
            payment_terms_name="Net 15",
            period_start=datetime.date(2026, 9, 15),
            period_end=datetime.date(2026, 10, 14),
            invoice_date=datetime.date(2026, 9, 15),
            due_date=datetime.date(2026, 9, 30),  # Overdue relative to 2026-10-31
            untaxed_amount=Decimal("3800.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("660.00"),
            total=Decimal("4460.00"),
            status="draft",
        )
        InvoiceLine.objects.create(
            invoice=inv_3,
            product=prod_suite,
            description="Brightloop Cloud Suite",
            quantity=2,
            unit_price=Decimal("1500.00"),
            tax_rate=Decimal("18.00"),
            amount=Decimal("3000.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("540.00"),
            is_addon=False,
        )
        InvoiceLine.objects.create(
            invoice=inv_3,
            product=prod_acct,
            description="Dedicated Account Manager",
            quantity=1,
            unit_price=Decimal("800.00"),
            tax_rate=Decimal("15.00"),
            amount=Decimal("800.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("120.00"),
            is_addon=True,
        )
        inv_3.status = "confirmed"
        inv_3.confirmed_at = now
        inv_3.save(update_fields=["status", "confirmed_at"])

    # 11. Payments
    if inv_1:
        Payment.objects.get_or_create(
            reference="PAY-000001",
            defaults={
                "invoice": inv_1,
                "method": "bank_transfer",
                "amount": inv_1.total,
                "payment_date": datetime.date(2026, 9, 10),
                "status": "succeeded",
                "note": "Settled via wire transfer #WT-88219",
                "recorded_by": admin_user,
            },
        )


def reverse_seed_data(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_auditlog"),
        ("catalog", "0002_paymentterm"),
        ("plans", "0001_initial"),
        ("discounts", "0001_initial"),
        ("subscriptions", "0001_initial"),
        ("billing", "0001_initial"),
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_demo_data, reverse_seed_data),
    ]
