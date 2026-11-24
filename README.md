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
yarn dev
```

`yarn dev` runs the Flask server on port 3000 and Vite's dev server on port 5173, which serves the React app in `src/` to the Flask page and updates it as you edit. (`python manage.py run_server` on its own serves the last `yarn build` instead.) Then open http://localhost:3000/offerings/157/ (the course `seed_data` sets up) and sign in. Without `CANVAS_CLIENT_ID`, signing in goes to a development login, where you can be anyone, as a TA or a student in every course. The database is SQLite (`app.db`) unless `.env` sets `DATABASE_URL`. To sign in with bCourses instead, set `CANVAS_CLIENT_ID` and `CANVAS_CLIENT_SECRET` in `.env` to the UC Berkeley sandbox's developer key.

`seed_data` adds sample assignments, locations, students and tickets. `python manage.py resetdb` starts the database over.

## Deployment

The app runs on Google Cloud Run, like seating and sections, from the `Dockerfile`: one non-root gunicorn worker with threads, with a health check at `/health`. The image builds the frontend with Vite (`yarn build`, into `oh_queue/static/dist/`), and Flask adds the bundle to the course page (`oh_queue/vite.py`). It connects to Cloud SQL as the service account it runs as (`CLOUD_SQL_INSTANCE`, `DB_USER`, `DB_NAME`), so no database password is stored, and gets its other secrets from Secret Manager.

Each pull request from a branch in this repository is deployed as a preview on the staging project (`.github/workflows/pr-staging.yml`), and the preview's URL is commented on the PR. Previews share the staging database and never run migrations; see [docs/migrations.md](docs/migrations.md).

## Running tests

With the packages installed as above:

```
pytest
flake8
```

The tests set their own settings and database, so they don't need a `.env` or Node. For the frontend:

```
yarn typecheck
yarn lint
yarn build
```

The end to end tests open every page of a course in headless Chrome, as staff and as a student, and request and resolve a ticket. They need Chrome and the build, so `pytest` leaves them out:

```
yarn build
pytest tests/e2e
```

The accessibility audit checks every page against WCAG 2.1 AA with axe-core, also in headless Chrome: `pytest tests/a11y`, after `yarn build`. See [docs/a11y.md](docs/a11y.md).

CI runs all of these on every pull request, the server tests with coverage (`.github/workflows/test.yml`, `e2e.yml`, `a11y.yml`), along with flake8, a dependency audit, and CodeQL.
