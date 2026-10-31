from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        """One normalization for every entry point: trimmed and lower-cased."""
        return (email or "").strip().lower()

    def get_by_natural_key(self, email):
        return self.get(email__iexact=self.normalize_email(email))

    def create_user(self, email, password=None, role=None):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(
            email=self.normalize_email(email),
            role=role or User.Role.CUSTOMER,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None):
        """Used by `manage.py createsuperuser`; creates an Admin-role account."""
        return self.create_user(email, password, role=User.Role.ADMIN)


class User(AbstractBaseUser):
    """Login identity. Email is the username; the persisted role is authoritative."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"
        CUSTOMER = "customer", "Customer"

    email = models.EmailField(max_length=254, unique=True)
    role = models.CharField(max_length=16, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
            models.CheckConstraint(
                condition=models.Q(role__in=["admin", "staff", "customer"]),
                name="accounts_user_role_valid",
            ),
        ]

    def __str__(self):
        return self.email

    # Django's admin site (mounted at /admin/) asks for these. They are derived
    # from the role, never stored, so no form field can escalate privileges.
    @property
    def is_staff(self):
        return self.role == self.Role.ADMIN

    @property
    def is_superuser(self):
        return self.role == self.Role.ADMIN

    def has_perm(self, perm, obj=None):
        return self.is_active and self.role == self.Role.ADMIN

    def has_module_perms(self, app_label):
        return self.is_active and self.role == self.Role.ADMIN


class Customer(models.Model):
    """Customer profile linked to a Customer-role user."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.user.email


class AuthAttempt(models.Model):
    """Database-backed counter for throttling (stateless-serverless safe)."""

    scope = models.CharField(max_length=32)
    key = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["scope", "key", "created_at"])]


class AuditLog(models.Model):
    """Who changed what and when (NFR-5). Written only through apps.accounts.audit."""

    actor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )  # null = the system (scheduled jobs)
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=64)
    target_id = models.PositiveBigIntegerField()
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(
                fields=["target_type", "target_id", "created_at"], name="accounts_audit_target_idx"
            )
        ]
