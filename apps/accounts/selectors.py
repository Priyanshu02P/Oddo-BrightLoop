from .models import Customer, User


def email_exists(email):
    return User.objects.filter(email__iexact=User.objects.normalize_email(email)).exists()


def get_customer_for_user(user):
    """Return the Customer profile of an authenticated Customer-role user."""
    if not user.is_authenticated or user.role != User.Role.CUSTOMER:
        return None
    return Customer.objects.filter(user_id=user.pk).first()


def list_internal_users():
    return User.objects.filter(role__in=[User.Role.ADMIN, User.Role.STAFF]).order_by("email")
