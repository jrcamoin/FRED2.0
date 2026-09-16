"""Authenticated platform pages."""

from flask import Blueprint, current_app, redirect, render_template, url_for
from flask_login import current_user, login_required

from robot import Robot, RobotState


main_blueprint = Blueprint("main", __name__)


@main_blueprint.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_blueprint.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@main_blueprint.get("/robot")
@login_required
def robot_page():
    robot: Robot = current_app.extensions["humanframe_robot"]
    components = (
        ("Face", "NEUTRAL"),
        ("Microphone", "NOT CONNECTED / SIMULATED"),
        ("Speaker", "NOT CONNECTED / SIMULATED"),
        ("Motors", "SIMULATED"),
    )
    return render_template(
        "robot.html",
        robot=robot,
        components=components,
        available_states=RobotState,
    )
