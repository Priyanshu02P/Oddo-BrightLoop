import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


def codes(password):
    with pytest.raises(ValidationError) as info:
        validate_password(password)
    return {e.code for e in info.value.error_list}


def test_eight_characters_rejected():
    assert codes("Abcde!f1") == {"password_too_short"}


def test_nine_characters_with_all_classes_accepted():
    validate_password("Abcdef!g1")


def test_no_uppercase_rejected():
    assert codes("abcdefgh!1") == {"password_no_upper"}


def test_no_lowercase_rejected():
    assert codes("ABCDEFGH!1") == {"password_no_lower"}


def test_no_special_character_rejected():
    assert codes("Abcdefghi1") == {"password_no_special"}


def test_space_is_not_a_special_character():
    assert codes("Abcdefgh 1") == {"password_no_special"}


def test_every_unmet_rule_is_reported():
    assert codes("abc") == {
        "password_too_short",
        "password_no_upper",
        "password_no_special",
    }
