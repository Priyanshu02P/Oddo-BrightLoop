import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Customer
from apps.catalog.models import PaymentTerm, Product, Tax
from apps.plans.models import Plan
from apps.subscriptions.models import Subscription, SubscriptionLine
from apps.billing.models import Invoice, InvoiceLine, BillingRun, BillingRunResult
from apps.payments.models import Payment

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds comprehensive UI mock and demo data for Brightloop"

    def handle(self, *args, **options):
        today = timezone.now().date()
        now = timezone.now()

        admin_user, _ = User.objects.get_or_create(
            email="admin@brightloop.com",
            defaults={
                "role": "admin",
                "is_active": True,
                "password": make_password("Admin#12345"),
                "date_joined": now,
            },
        )

        tax_none, _ = Tax.objects.get_or_create(name="No Tax (0%)", defaults={"rate": Decimal("0.00")})
        tax_std, _ = Tax.objects.get_or_create(name="Standard Tax (15%)", defaults={"rate": Decimal("15.00")})

        term_due, _ = PaymentTerm.objects.get_or_create(name="Immediate", defaults={"days": 0})
        term_net30, _ = PaymentTerm.objects.get_or_create(name="Net 30", defaults={"days": 30})

        # Products
        prod_starter, _ = Product.objects.get_or_create(
            name="Starter Package",
            defaults={"type": "service", "sales_price": Decimal("89.00"), "cost_price": Decimal("30.00"), "tax": tax_std},
        )
        prod_growth, _ = Product.objects.get_or_create(
            name="Growth Platform",
            defaults={"type": "service", "sales_price": Decimal("240.00"), "cost_price": Decimal("80.00"), "tax": tax_std},
        )
        prod_scale, _ = Product.objects.get_or_create(
            name="Scale Platform",
            defaults={"type": "service", "sales_price": Decimal("2400.00"), "cost_price": Decimal("800.00"), "tax": tax_std},
        )

        # Plans
        plan_starter, _ = Plan.objects.get_or_create(
            name="Starter · Monthly",
            defaults={
                "price": Decimal("89.00"),
                "billing_period": "monthly",
                "minimum_quantity": 1,
                "availability_start_date": datetime.date(2024, 1, 1),
                "availability_end_date": datetime.date(2030, 12, 31),
                "renewal_mode": "automatic",
                "allow_pause": True,
                "allow_renew": True,
            },
        )
        plan_growth, _ = Plan.objects.get_or_create(
            name="Growth · Monthly",
            defaults={
                "price": Decimal("240.00"),
                "billing_period": "monthly",
                "minimum_quantity": 1,
                "availability_start_date": datetime.date(2024, 1, 1),
                "availability_end_date": datetime.date(2030, 12, 31),
                "renewal_mode": "automatic",
                "allow_pause": True,
                "allow_renew": True,
            },
        )
        plan_scale, _ = Plan.objects.get_or_create(
            name="Scale · Yearly",
            defaults={
                "price": Decimal("2400.00"),
                "billing_period": "yearly",
                "minimum_quantity": 1,
                "availability_start_date": datetime.date(2024, 1, 1),
                "availability_end_date": datetime.date(2030, 12, 31),
                "renewal_mode": "automatic",
                "allow_pause": True,
                "allow_renew": True,
            },
        )

        # Customers
        customers_data = [
            ("Northstar Studio", "billing@northstar.studio"),
            ("Atlas & Co.", "finance@atlasandco.com"),
            ("Morrow Goods", "ops@morrowgoods.com"),
            ("Kite & Pixel", "hello@kitepixel.co"),
            ("Harbor Labs", "ap@harborlabs.io"),
            ("Quill Analytics", "accounts@quill.ai"),
            ("Fable & Fern", "accounts@fableandfern.com"),
        ]

        customer_objs = {}
        for name, email in customers_data:
            u, _ = User.objects.get_or_create(
                email=email,
                defaults={"role": "customer", "password": make_password("Customer#12345"), "is_active": True},
            )
            c, _ = Customer.objects.get_or_create(user=u)
            customer_objs[name] = c

        # Subscriptions
        subs_spec = [
            ("SUB-0412", "Northstar Studio", plan_growth, "active", today - datetime.timedelta(days=90), today + datetime.timedelta(days=275), today + datetime.timedelta(days=2), False),
            ("SUB-0409", "Atlas & Co.", plan_scale, "active", today - datetime.timedelta(days=180), today + datetime.timedelta(days=185), today + datetime.timedelta(days=4), False),
            ("SUB-0405", "Harbor Labs", plan_growth, "active", today - datetime.timedelta(days=60), today + datetime.timedelta(days=305), today + datetime.timedelta(days=1), True),
            ("SUB-0398", "Morrow Goods", plan_starter, "paused", today - datetime.timedelta(days=120), today + datetime.timedelta(days=245), today + datetime.timedelta(days=31), False),
            ("SUB-0417", "Quill Analytics", plan_scale, "confirmed", today + datetime.timedelta(days=15), today + datetime.timedelta(days=380), today + datetime.timedelta(days=15), False),
            ("SUB-0418", "Kite & Pixel", plan_growth, "quotation", today + datetime.timedelta(days=7), today + datetime.timedelta(days=372), today + datetime.timedelta(days=7), False),
            ("SUB-0352", "Fable & Fern", plan_starter, "closed", today - datetime.timedelta(days=300), today - datetime.timedelta(days=19), None, False),
        ]

        sub_objs = {}
        for num, cust_name, plan, status, start, expiry, next_bill, failed in subs_spec:
            s, _ = Subscription.objects.get_or_create(
                number=num,
                defaults={
                    "customer": customer_objs[cust_name],
                    "plan": plan,
                    "payment_terms": term_net30,
                    "status": status,
                    "start_date": start,
                    "expiry_date": expiry,
                    "next_billing_date": next_bill,
                    "payment_failed": failed,
                    "quotation_validity_days": 30,
                },
            )
            # Add line
            if not s.lines.exists():
                SubscriptionLine.objects.create(
                    subscription=s,
                    product=prod_growth if "Growth" in plan.name else (prod_scale if "Scale" in plan.name else prod_starter),
                    quantity=1,
                    unit_price=plan.price,
                    tax_rate=Decimal("15.00"),
                    amount=plan.price,
                    tax_amount=(plan.price * Decimal("0.15")).quantize(Decimal("0.01")),
                )
            sub_objs[num] = s

        # Invoices
        inv_spec = [
            ("INV-1048", sub_objs["SUB-0412"], "Northstar Studio", "confirmed", today - datetime.timedelta(days=30), today - datetime.timedelta(days=1), Decimal("2156.52"), Decimal("323.48"), Decimal("2480.00")),
            ("INV-1047", sub_objs["SUB-0409"], "Atlas & Co.", "confirmed", today - datetime.timedelta(days=10), today + datetime.timedelta(days=20), Decimal("1669.57"), Decimal("250.43"), Decimal("1920.00")),
            ("INV-1046", sub_objs["SUB-0398"], "Morrow Goods", "draft", today - datetime.timedelta(days=2), today + datetime.timedelta(days=28), Decimal("747.83"), Decimal("112.17"), Decimal("860.00")),
            ("INV-1045", sub_objs["SUB-0418"], "Kite & Pixel", "paid", today - datetime.timedelta(days=40), today - datetime.timedelta(days=10), Decimal("2782.61"), Decimal("417.39"), Decimal("3200.00")),
            ("INV-1044", sub_objs["SUB-0405"], "Harbor Labs", "confirmed", today - datetime.timedelta(days=45), today - datetime.timedelta(days=15), Decimal("626.09"), Decimal("93.91"), Decimal("720.00")),
            ("INV-1039", sub_objs["SUB-0352"], "Fable & Fern", "cancelled", today - datetime.timedelta(days=70), today - datetime.timedelta(days=40), Decimal("77.39"), Decimal("11.61"), Decimal("89.00")),
        ]

        inv_objs = {}
        for num, sub, cust_name, status, inv_date, due_date, untaxed, tax, total in inv_spec:
            inv, _ = Invoice.objects.get_or_create(
                number=num,
                defaults={
                    "subscription": sub,
                    "customer": customer_objs[cust_name],
                    "customer_email": customer_objs[cust_name].user.email,
                    "plan_name": sub.plan.name,
                    "payment_terms_name": "Net 30",
                    "period_start": inv_date,
                    "period_end": inv_date + datetime.timedelta(days=30),
                    "invoice_date": inv_date,
                    "due_date": due_date,
                    "status": status,
                    "untaxed_amount": untaxed,
                    "discount_amount": Decimal("0.00"),
                    "tax_amount": tax,
                    "total": total,
                    "confirmed_at": now if status in ["confirmed", "paid"] else None,
                    "paid_at": now if status == "paid" else None,
                    "cancelled_at": now if status == "cancelled" else None,
                },
            )
            inv_objs[num] = inv

        # Payments
        pay_spec = [
            ("PAY-8391", inv_objs["INV-1048"], "card", Decimal("2480.00"), "succeeded", today - datetime.timedelta(days=1)),
            ("PAY-8390", inv_objs["INV-1047"], "bank_transfer", Decimal("1920.00"), "succeeded", today - datetime.timedelta(days=2)),
            ("PAY-8389", inv_objs["INV-1044"], "card", Decimal("720.00"), "failed", today - datetime.timedelta(days=2)),
            ("PAY-8388", inv_objs["INV-1045"], "card", Decimal("3200.00"), "succeeded", today - datetime.timedelta(days=3)),
            ("PAY-8387", inv_objs["INV-1046"], "cash", Decimal("860.00"), "succeeded", today - datetime.timedelta(days=4)),
        ]

        for ref, inv, method, amount, status, pdate in pay_spec:
            Payment.objects.get_or_create(
                reference=ref,
                defaults={
                    "invoice": inv,
                    "method": method,
                    "amount": amount,
                    "status": status,
                    "payment_date": pdate,
                    "recorded_by": admin_user,
                    "failure_reason": "Card declined · insufficient funds" if status == "failed" else "",
                },
            )

        # Billing Runs
        runs_spec = [
            ("manual", admin_user, "completed", today, now - datetime.timedelta(hours=9), now - datetime.timedelta(hours=9, seconds=-41), 190, 182, 6, 2),
            ("scheduled", None, "completed", today - datetime.timedelta(days=1), now - datetime.timedelta(days=1, hours=9), now - datetime.timedelta(days=1, hours=9, seconds=-35), 13, 12, 1, 0),
            ("scheduled", None, "completed", today - datetime.timedelta(days=2), now - datetime.timedelta(days=2, hours=9), now - datetime.timedelta(days=2, hours=9, seconds=-28), 9, 9, 0, 0),
            ("scheduled", None, "completed", today - datetime.timedelta(days=3), now - datetime.timedelta(days=3, hours=9), now - datetime.timedelta(days=3, hours=9, seconds=-45), 18, 15, 2, 1),
        ]

        for trig, actor, st, rdate, start_t, fin_t, proc, cre, skip, fail in runs_spec:
            run, created = BillingRun.objects.get_or_create(
                run_date=rdate,
                defaults={
                    "trigger": trig,
                    "triggered_by": actor,
                    "status": st,
                    "started_at": start_t,
                    "finished_at": fin_t,
                },
            )
            if created and not run.results.exists():
                # Add sample results
                BillingRunResult.objects.create(
                    run=run,
                    subscription=sub_objs["SUB-0412"],
                    outcome="created",
                    invoice=inv_objs["INV-1048"],
                )
                if fail > 0:
                    BillingRunResult.objects.create(
                        run=run,
                        subscription=sub_objs["SUB-0405"],
                        outcome="failed",
                        reason="Product 'Growth seat' has no tax configured",
                    )
                if skip > 0:
                    BillingRunResult.objects.create(
                        run=run,
                        subscription=sub_objs["SUB-0398"],
                        outcome="skipped",
                        reason="Subscription is paused",
                    )

        self.stdout.write(self.style.SUCCESS("Successfully seeded UI mock data!"))
