from django import template

from apps.accounts.permissions import Permission, has_permission

register = template.Library()


@register.filter
def can(user, permission_name):
    """Template helper: {% if user|can:"manage_users" %}. UI visibility only;
    the server still enforces every permission."""
    return has_permission(user, Permission(permission_name))
