from .models import AuditLog


def record_audit(*, actor, action, target, from_status="", to_status=""):
    """Append an audit entry for `target`. `actor=None` means the system."""
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target._meta.label_lower,
        target_id=target.pk,
        from_status=from_status,
        to_status=to_status,
    )
