"""Authentication and registration operations."""

import re

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from .models import User


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,80}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegistrationError(ValueError):
    """A user-facing registration validation error."""


def register_user(username: str, email: str, password: str) -> User:
    """Validate and persist a new local user."""
    clean_username = username.strip()
    clean_email = email.strip().lower()

    if not USERNAME_PATTERN.fullmatch(clean_username):
        raise RegistrationError(
            "Username must be 3–80 characters using letters, numbers, dots, dashes, or underscores."
        )
    if not EMAIL_PATTERN.fullmatch(clean_email) or len(clean_email) > 255:
        raise RegistrationError("Enter a valid email address.")
    if len(password) < 8:
        raise RegistrationError("Password must contain at least 8 characters.")

    duplicate = db.session.scalar(
        select(User).where(
            or_(User.username == clean_username, User.email == clean_email)
        )
    )
    if duplicate:
        raise RegistrationError("That username or email is already registered.")

    user = User(
        username=clean_username,
        email=clean_email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise RegistrationError(
            "That username or email is already registered."
        ) from error
    return user


def authenticate(identifier: str, password: str) -> User | None:
    """Return the matching user only when the supplied password is valid."""
    clean_identifier = identifier.strip()
    if not clean_identifier or not password:
        return None

    user = db.session.scalar(
        select(User).where(
            or_(User.username == clean_identifier, User.email == clean_identifier)
        )
    )
    if user and check_password_hash(user.password_hash, password):
        return user
    return None
