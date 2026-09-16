"""Development entry point for the HumanFrame web application."""

from system import create_app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, load_dotenv=False)
