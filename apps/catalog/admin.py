from django.contrib import admin

from .models import PaymentTerm, Tax

# Tax and PaymentTerm were previously managed only via Django admin.
# They now have dedicated M9 UI screens at /app/catalog/taxes/ and
# /app/catalog/payment-terms/. The admin registration is kept as a backup.
admin.site.register(Tax)
admin.site.register(PaymentTerm)
