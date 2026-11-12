"""Fernet-based token encryption for SCM connection secrets."""

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenEncryptionError(Exception):
    """Raised when token encryption or decryption fails."""


def _get_encryption_key() -> str:
    """Return the secret used for token encryption.

    Precedence:
    1. TOKEN_ENCRYPTION_KEY (dedicated, recommended)
    2. SESSION_SECRET / WORKOS_SESSION_SECRET (backward compat)

    Never falls back to a hardcoded value. Raises immediately if no key is
    configured so that misconfigured deployments fail fast.
    """
    if settings.token_encryption_key:
        return settings.token_encryption_key

    secret = (settings.session_secret or settings.workos_session_secret or "").strip()
    if secret:
        logger.warning(
            "TOKEN_ENCRYPTION_KEY is not set — falling back to session secret. "
            "Set a dedicated TOKEN_ENCRYPTION_KEY for production use."
        )
        return secret

    raise TokenEncryptionError(
        "No encryption key configured. Set TOKEN_ENCRYPTION_KEY (recommended) "
        "or SESSION_SECRET before storing encrypted tokens."
    )


@lru_cache(maxsize=4)
def _build_cipher(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string and return the ciphertext."""
    return _build_cipher(_get_encryption_key()).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a ciphertext string and return the plaintext token."""
    try:
        return (
            _build_cipher(_get_encryption_key()).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        )
    except InvalidToken as exc:
        raise TokenEncryptionError("Failed to decrypt token — key may have changed") from exc
