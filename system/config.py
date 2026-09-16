"""Configuration helpers for the HumanFrame platform."""

import os
from pathlib import Path
from typing import Any

from flask import Flask


DEVELOPMENT_SECRET_KEY = "humanframe-development-only-change-me"


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def configure_app(app: Flask, overrides: dict[str, Any] | None = None) -> None:
    """Load environment-backed defaults, followed by optional test overrides."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        database_path = Path(app.instance_path) / "humanframe.db"
        database_url = f"sqlite:///{database_path}"

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", DEVELOPMENT_SECRET_KEY),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=_as_bool(os.environ.get("SESSION_COOKIE_SECURE")),
    )
    if overrides:
        app.config.update(overrides)
