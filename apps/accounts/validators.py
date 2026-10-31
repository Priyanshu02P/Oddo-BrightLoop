from django.core.exceptions import ValidationError

MIN_LENGTH_EXCLUSIVE = 8


class BrightloopPasswordValidator:
    """FR-1.3: more than 8 characters, with an uppercase letter, a lowercase
    letter and a special character (not a letter, digit or whitespace)."""

    def validate(self, password, user=None):
        errors = []
        if len(password) <= MIN_LENGTH_EXCLUSIVE:
            errors.append(
                ValidationError(
                    "Password must contain more than 8 characters.",
                    code="password_too_short",
                )
            )
        if not any(c.isupper() for c in password):
            errors.append(
                ValidationError(
                    "Password must contain at least one uppercase letter.",
                    code="password_no_upper",
                )
            )
        if not any(c.islower() for c in password):
            errors.append(
                ValidationError(
                    "Password must contain at least one lowercase letter.",
                    code="password_no_lower",
                )
            )
        if not any(not c.isalnum() and not c.isspace() for c in password):
            errors.append(
                ValidationError(
                    "Password must contain at least one special character.",
                    code="password_no_special",
                )
            )
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            "More than 8 characters, with at least one uppercase letter, "
            "one lowercase letter and one special character."
        )
