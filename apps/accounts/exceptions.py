class EmailAlreadyRegistered(Exception):
    """An account already exists for this email (compared case-insensitively)."""
