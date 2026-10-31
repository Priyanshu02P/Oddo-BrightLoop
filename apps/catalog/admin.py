from django.contrib import admin

from .models import Tax

# Interim: Taxes are administered by M9, which has no screen yet. Registering
# the model lets an Admin create the Tax records every product must reference.
# Products are deliberately not registered: catalog writes go through services.
admin.site.register(Tax)
