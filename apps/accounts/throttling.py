import hashlib
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import AuthAttempt, User

LOGIN = "login"
SIGNUP = "signup"
PASSWORD_RESET = "password_reset"

THROTTLE_MESSAGE = "Too many attempts. Please wait a while and try again."


def _digest(prefix, value):
    return hashlib.sha256(f"{prefix}:{value}".encode()).hexdigest()


def throttle_keys(request, email=None):
    """Hashed keys so no raw IP or email is stored."""
    ip = request.META.get(settings.THROTTLE_IP_HEADER, "unknown").split(",")[0].strip()
    keys = [_digest("ip", ip)]
    if email:
        keys.append(_digest("email", User.objects.normalize_email(email)))
    return keys


def is_throttled(scope, keys):
    limit, window = settings.AUTH_THROTTLE[scope]
    since = timezone.now() - timedelta(seconds=window)
    return any(
        AuthAttempt.objects.filter(scope=scope, key=key, created_at__gte=since).count() >= limit
        for key in keys
    )


def record_attempt(scope, keys):
    _, window = settings.AUTH_THROTTLE[scope]
    AuthAttempt.objects.bulk_create([AuthAttempt(scope=scope, key=key) for key in keys])
    AuthAttempt.objects.filter(
        scope=scope, created_at__lt=timezone.now() - timedelta(seconds=window)
    ).delete()
