"""Permission helpers for M6 Discounts — thin wrapper kept for symmetry with other apps."""

from apps.accounts.permissions import Permission, has_permission, require_permission  # noqa: F401

# The create_discount_rules permission is already defined in accounts.permissions.
# Re-export for convenience.
DISCOUNT_PERMISSION = Permission.CREATE_DISCOUNT_RULES
