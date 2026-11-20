# Office Hours Queue

## Overview

Provides a web-based interface for requesting help during office hours.

Students request help on an assignment and question number from a location.

Students and staff sign in with bCourses, and a person's staff role comes from their bCourses enrollment.

For now each deployment serves one course, set by `COURSE_KEY` and `CANVAS_COURSE_ID` (see `.env.example`).

## Installation

Requires Python 3.14 and Node 24 (`mise install` picks both up from `mise.toml`). On Windows, use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install). From the repository root:

```
cp .env.example .env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
yarn install
python manage.py initdb
python manage.py seed_data
python manage.py run_server
```

Then open http://localhost:3000 and sign in at `/testing-login/`. The database is SQLite (`app.db`) unless `.env` sets `DATABASE_URL`. To sign in with bCourses instead, set `CANVAS_CLIENT_ID` and `CANVAS_CLIENT_SECRET` in `.env` to the UC Berkeley sandbox's developer key.

`seed_data` adds sample assignments, locations, students and tickets. `python manage.py resetdb` starts the database over.

## Running tests

With the packages installed as above:

```
pytest
flake8
```

The tests set their own settings and database, so they don't need a `.env`. Rendering the page compiles the frontend, which is why they need the Node packages. CI runs them on every pull request, with coverage (`.github/workflows/test.yml`), along with flake8, a dependency audit, and CodeQL.

If you ever receive a `FileNotFoundError: ... .webassets-cache/...` error, the static file cache is corrupted, so delete the `.webassets-cache` folder in `oh_queue/static`. Then rebuild and run.
