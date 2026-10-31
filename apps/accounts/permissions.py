"""Central, default-deny RBAC layer (FR-1.5). Maps to REQUIREMENTS.md Section 4."""

from enum import StrEnum
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from . import selectors
from .models import User


class Permission(StrEnum):
    CREATE_STAFF = "create_staff"
    MANAGE_USERS = "manage_users"
    MANAGE_CATALOG = "manage_catalog"  # products, variants, plans
    MANAGE_TAXES_AND_PAYMENT_TERMS = "manage_taxes_and_payment_terms"
    CREATE_DISCOUNT_RULES = "create_discount_rules"
    MANAGE_QUOTATION_TEMPLATES = "manage_quotation_templates"
    USE_QUOTATION_TEMPLATES = "use_quotation_templates"
    MANAGE_SUBSCRIPTIONS = "manage_subscriptions"
    ACCEPT_QUOTATION = "accept_quotation"
    RUN_BILLING = "run_billing"
    MANAGE_INVOICES = "manage_invoices"  # confirm / cancel / send / print
    RECORD_PAYMENTS = "record_payments"
    VIEW_DASHBOARD = "view_dashboard"
    # Customer-portal capabilities. Callers must also scope data with
    # scope_to_customer().
    ACCESS_CUSTOMER_PORTAL = "access_customer_portal"
    MANAGE_OWN_SUBSCRIPTIONS = "manage_own_subscriptions"
    ACCEPT_OWN_QUOTATION = "accept_own_quotation"
    VIEW_OWN_INVOICES = "view_own_invoices"
    VIEW_OWN_PAYMENTS = "view_own_payments"


_P = Permission

_INTERNAL_SHARED = frozenset(
    {
        _P.USE_QUOTATION_TEMPLATES,
        _P.MANAGE_SUBSCRIPTIONS,
        _P.ACCEPT_QUOTATION,
        _P.RUN_BILLING,
        _P.MANAGE_INVOICES,
        _P.RECORD_PAYMENTS,
        _P.VIEW_DASHBOARD,
    }
)

ROLE_PERMISSIONS = {
    User.Role.ADMIN: _INTERNAL_SHARED
    | {
        _P.CREATE_STAFF,
        _P.MANAGE_USERS,
        _P.MANAGE_CATALOG,
        _P.MANAGE_TAXES_AND_PAYMENT_TERMS,
        _P.CREATE_DISCOUNT_RULES,
        _P.MANAGE_QUOTATION_TEMPLATES,
    },
    User.Role.STAFF: _INTERNAL_SHARED,
    User.Role.CUSTOMER: frozenset(
        {
            _P.ACCESS_CUSTOMER_PORTAL,
            _P.MANAGE_OWN_SUBSCRIPTIONS,
            _P.ACCEPT_OWN_QUOTATION,
            _P.VIEW_OWN_INVOICES,
            _P.VIEW_OWN_PAYMENTS,
        }
    ),
}


def has_permission(user, permission):
    """Default deny: anonymous, inactive, unknown-role and unlisted all fail."""
    if not (user and user.is_authenticated and user.is_active):
        return False
    return permission in ROLE_PERMISSIONS.get(user.role, frozenset())


def require_permission(permission):
    """View decorator: anonymous -> sign-in; authenticated but denied -> 403."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not has_permission(request.user, permission):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def scope_to_customer(queryset, user, lookup="customer"):
    """Restrict a queryset to the authenticated Customer's own records (FR-1.7).

    Always look records up through this (e.g. get_object_or_404 on the scoped
    queryset), never by primary key alone. Non-customers are denied.
    """
    customer = selectors.get_customer_for_user(user)
    if customer is None:
        raise PermissionDenied
    return queryset.filter(**{lookup: customer})


def landing_url_name(user):
    """Role-based post-login destination."""
    if user.role == User.Role.CUSTOMER:
        return "accounts:portal_home"
    return "accounts:internal_home"
