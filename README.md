# Office Hours Queue

## Overview

Provides a web-based interface for requesting help during office hours.

Students request help on an assignment and question number from a location.

Students and staff sign in with bCourses, and a person's staff role in each course comes from their bCourses enrollment.

One site serves every course, with seating's and sections' routes: after signing in, `/offerings` lists your courses, and each course's queue is at `/offerings/<bCourses course id>/`. Course staff set up a queue for one of their bCourses courses with **Import courses from Canvas**. A course moved from one of the old per-course sites keeps its data under its old key (such as `cs61a`): a maintainer links it to its bCourses course with `python manage.py link-offering <bCourses course id> <key> "<name>"`.

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

Then open http://localhost:3000/offerings/157/ (the course `seed_data` sets up) and sign in. Without `CANVAS_CLIENT_ID`, signing in goes to a development login, where you can be anyone, as a TA or a student in every course. The database is SQLite (`app.db`) unless `.env` sets `DATABASE_URL`. To sign in with bCourses instead, set `CANVAS_CLIENT_ID` and `CANVAS_CLIENT_SECRET` in `.env` to the UC Berkeley sandbox's developer key.

`seed_data` adds sample assignments, locations, students and tickets. `python manage.py resetdb` starts the database over.

## Deployment

The app runs on Google Cloud Run, like seating and sections, from the `Dockerfile`: one non-root gunicorn worker with threads, with a health check at `/health`. The image builds the frontend with `flask build`, since in production the app serves `oh_queue/static/public/` as it is. It connects to Cloud SQL as the service account it runs as (`CLOUD_SQL_INSTANCE`, `DB_USER`, `DB_NAME`), so no database password is stored, and gets its other secrets from Secret Manager.

Each pull request from a branch in this repository is deployed as a preview on the staging project (`.github/workflows/pr-staging.yml`), and the preview's URL is commented on the PR. Previews share the staging database and never run migrations; see [docs/migrations.md](docs/migrations.md).

## Running tests

With the packages installed as above:

```
pytest
flake8
```

The tests set their own settings and database, so they don't need a `.env`. Rendering the page compiles the frontend, which is why they need the Node packages. CI runs them on every pull request, with coverage (`.github/workflows/test.yml`), along with flake8, a dependency audit, and CodeQL.

If you ever receive a `FileNotFoundError: ... .webassets-cache/...` error, the static file cache is corrupted, so delete the `.webassets-cache` folder in `oh_queue/static`. Then rebuild and run.
