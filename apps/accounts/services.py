import logging

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction

from . import selectors
from .exceptions import EmailAlreadyRegistered
from .models import Customer, User
from .permissions import Permission, has_permission

logger = logging.getLogger(__name__)


def _create_account(*, email, password, role):
    try:
        with transaction.atomic():
            user = User.objects.create_user(email, password, role=role)
            if role == User.Role.CUSTOMER:
                Customer.objects.create(user=user)
    except IntegrityError:
        # The database constraint is the final authority on uniqueness.
        if selectors.email_exists(email):
            raise EmailAlreadyRegistered from None
        raise
    return user


def register_customer(*, email, password):
    """Public signup (FR-1.1, FR-1.6): always creates a Customer."""
    return _create_account(email=email, password=password, role=User.Role.CUSTOMER)


def create_staff_account(*, actor, email, password):
    """Admin-only Staff creation (FR-1.6). Authorization is checked here too, so
    the service is safe if called from any entry point."""
    if not has_permission(actor, Permission.CREATE_STAFF):
        raise PermissionDenied
    user = _create_account(email=email, password=password, role=User.Role.STAFF)
    logger.info("Staff account %s created by user %s", user.pk, actor.pk)
    return user
