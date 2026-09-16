# HumanFrame Robotics

A clean development baseline for the HumanFrame Robotics platform. The project
keeps web-platform concerns under `system/` and robot-specific domain code under
`robot/` so authentication and Flask infrastructure do not leak into future
simulation, behavior, or hardware work.

The `old/` directory is reference material only. The new application does not
import or depend on it.

## Setup

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with
`.venv\Scripts\Activate.ps1` instead.

## Run the application

From the repository root:

```bash
python app.py
```

Open <http://127.0.0.1:5000>. Register a local account, then use the dashboard
and Robot UI. The SQLite database is created automatically at
`instance/humanframe.db`.

For a non-default development secret or database, export environment variables
before starting the app:

```bash
export SECRET_KEY="replace-with-a-long-random-value"
export DATABASE_URL="sqlite:////absolute/path/to/humanframe.db"
python app.py
```

Set `SESSION_COOKIE_SECURE=true` only when the site is served over HTTPS. The
development defaults are convenient for local work, not production deployment.

## Run the tests

```bash
python -m unittest discover -s tests -v
```

The suite covers imports, homepage redirects, registration, duplicate-user
rejection, password hashing, valid and invalid login, authenticated pages,
logout, route protection, Robot UI status, and the initial robot states.

## Project structure

```text
.
├── app.py                    # python app.py entry point
├── requirements.txt
├── pyproject.toml
├── system/                   # Flask platform and user-facing system UI
│   ├── app.py                # application factory
│   ├── config.py
│   ├── extensions.py
│   ├── auth/                 # user model, auth services, routes
│   ├── routes/               # authenticated application pages
│   ├── templates/            # shared layout and page templates
│   └── static/css/           # shared visual design
├── robot/                    # robot domain, independent of Flask
│   ├── robot.py              # minimal Robot coordinator shell
│   ├── state.py              # RobotState enum
│   ├── simulation/           # future simulated device adapters
│   ├── hardware/             # future physical device adapters
│   └── behaviors/            # future high-level behaviors
├── tests/
└── old/                      # untouched reference implementation
```

## What works now

- Flask application factory and blueprints
- Local registration with duplicate username/email protection
- Werkzeug password hashing
- Flask-Login session authentication
- CSRF protection for authentication and logout forms
- Login with either username or email
- Authenticated dashboard and Robot UI
- Shared responsive navigation and page styling
- SQLite persistence with no manual database setup
- Importable `RobotState` enum and minimal `Robot.set_state(...)`

## What is simulated

The Robot UI reports the initial `IDLE` robot state, a neutral face, simulated or
disconnected microphone and speaker, and simulated motors. These are debug labels
only; they do not pretend that device APIs exist.

## Not implemented yet

- State transitions or a state-machine event loop
- Simulated microphone, speaker, face/display, or motor objects
- Physical hardware drivers, GPIO, PWM, serial, or audio pipelines
- Behaviors, behavior trees, ROS, LLM, or remote service integrations
- OAuth, JWT, roles/permissions, password reset, or production deployment
- Database migrations or production secret management

## Where to build next

Start in `robot/simulation/` by defining one small simulated device at a time.
Introduce matching device interfaces before physical adapters, then evolve
`Robot` from its current state holder into the coordinator for explicit state
transitions. Connect state changes to the `/robot` page only after the robot
domain can be tested without Flask.
