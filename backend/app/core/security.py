"""Password hashing and random tokens."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # Argon2id with the library's recommended parameters
_DUMMY_HASH = _hasher.hash("timing-equalizer")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def verify_password_against_nothing(password: str) -> None:
    """Spend the same time as a real check, so response times don't reveal which emails exist."""
    verify_password(_DUMMY_HASH, password)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_token() -> str:
    """A random, URL-safe secret for cookies and email links (256 bits)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are stored hashed: a leaked database can't be used to log in."""
    return hashlib.sha256(token.encode()).hexdigest()
