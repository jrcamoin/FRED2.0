"""Flask application factory."""

from pathlib import Path
from typing import Any

from flask import Flask

from robot import Robot

from .config import configure_app
from .extensions import csrf, db, login_manager


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Create and configure an isolated HumanFrame application instance."""
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        template_folder="templates",
    )
    configure_app(app, test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    from .auth.models import User
    from .auth.routes import auth_blueprint
    from .routes.main import main_blueprint

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)

    # App-local domain state keeps Flask setup separate from robot behavior.
    app.extensions["humanframe_robot"] = Robot()

    with app.app_context():
        db.create_all()

    return app
