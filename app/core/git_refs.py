"""Validation for branch names and detached commit IDs supplied to Git."""

import re


def validate_branch(value: str | None) -> str | None:
    """Accept Git branch names, including refs/heads/ names, without revision syntax."""
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value
        or value.startswith(("-", "/"))
        or value.removeprefix("refs/heads/").startswith("-")
        or value == "@"
        or value.endswith(("/", "."))
        or ".." in value
        or "@{" in value
        or "//" in value
        or any(ord(c) < 32 or ord(c) == 127 or c in " ~^:?*[\\" for c in value)
        or any(part.startswith(".") or part.endswith(".lock") for part in value.split("/"))
    ):
        raise ValueError("Invalid Git branch name")
    return value


def validate_commit(value: str | None) -> str | None:
    """Accept SHA-1 or SHA-256 object IDs, abbreviated to at least seven hex digits."""
    if value is not None and (
        not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{7,64}", value)
    ):
        raise ValueError("Commit must be a 7 to 64 character hexadecimal object ID")
    return value
