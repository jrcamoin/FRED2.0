"""Database models owned by the authentication subsystem."""

from flask_login import UserMixin

from ..extensions import db


class User(UserMixin, db.Model):
    """A local development user authenticated with a password."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(80, collation="NOCASE"), unique=True, nullable=False, index=True
    )
    email = db.Column(
        db.String(255, collation="NOCASE"), unique=True, nullable=False, index=True
    )
    password_hash = db.Column(db.String(512), nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.username!r}>"
