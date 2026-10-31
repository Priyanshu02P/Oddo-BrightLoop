from .models import Plan


def list_plans():
    return Plan.objects.order_by("name", "id")


def list_plans_available_on(start_date):
    """Plans the subscription form may offer for the selected start date (FR-3.5)."""
    return Plan.objects.available_on(start_date).order_by("name", "id")


def list_plans_pending_auto_close(today):
    """Plans with auto-close enabled whose end date is before `today` (FR-3.6)."""
    return Plan.objects.pending_auto_close(today).order_by("id")
