"""Authentication routes."""

from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from .services import RegistrationError, authenticate, register_user


auth_blueprint = Blueprint("auth", __name__)


def _safe_next_url(candidate: str | None) -> str | None:
    """Allow only local absolute-path redirects after login."""
    if not candidate:
        return None
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc or not candidate.startswith("/"):
        return None
    return candidate


@auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        user = authenticate(
            request.form.get("identifier", ""), request.form.get("password", "")
        )
        if user is None:
            flash("Invalid username/email or password.", "error")
            return render_template(
                "login.html", next_url=_safe_next_url(request.form.get("next"))
            ), 401

        login_user(user)
        destination = _safe_next_url(request.form.get("next"))
        return redirect(destination or url_for("main.dashboard"))

    return render_template("login.html", next_url=_safe_next_url(request.args.get("next")))


@auth_blueprint.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        try:
            user = register_user(
                request.form.get("username", ""),
                request.form.get("email", ""),
                request.form.get("password", ""),
            )
        except RegistrationError as error:
            flash(str(error), "error")
            return render_template("register.html"), 400

        login_user(user)
        flash("Account created. Welcome to HumanFrame.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("register.html")


@auth_blueprint.post("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
