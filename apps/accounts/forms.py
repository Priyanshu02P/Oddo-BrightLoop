from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from . import selectors
from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    """Sign-in with email. The inherited invalid-login error is deliberately
    generic and does not say which credential was wrong."""

    username = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )


class AccountCreationForm(forms.Form):
    """Used for public Customer signup and Admin-created Staff accounts.

    Only the declared fields are read, so any submitted role, is_staff or
    is_superuser value is ignored.
    """

    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if selectors.email_exists(email):
            raise ValidationError(
                "This email address can't be used to create another account. "
                "If it is yours, sign in or reset your password.",
                code="duplicate_email",
            )
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two passwords do not match.")
        if password1:
            try:
                validate_password(password1)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned
