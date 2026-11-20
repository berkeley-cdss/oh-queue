# Office Hours Queue

## Overview

Provides a web-based interface for requesting help during office hours.

Students request help on an assignment and question number from a location.

Students and staff sign in with bCourses, and a person's staff role comes from their bCourses enrollment.

For now each deployment serves one course, set by `COURSE_KEY` and `CANVAS_COURSE_ID` (see `.env.example`).

## Installation

We supply a `Dockerfile.dev` which mimics the production environment.

1. Copy `.env.example` to `.env`. To sign in with bCourses locally, set `CANVAS_CLIENT_ID` and `CANVAS_CLIENT_SECRET` to the UC Berkeley sandbox's developer key. Otherwise, sign in at `/testing-login/`.
2. From the repository root, run
   ```
   docker build --no-cache -f Dockerfile.dev -t oh:dev .
   docker run --rm -p 3000:3000 -v "${PWD}:/app" --env-file .env --name oh-dev oh:dev
   ```
3. In another terminal, set up the database:
   ```
   docker exec -it oh-dev python manage.py initdb
   docker exec -it oh-dev python manage.py seed_data
   ```
4. The server is now running on http://localhost:3000.

If you ever receive a `FileNotFoundError: ... .webassets-cache/...` error, the static file cache is corrupted, so delete the `.webassets-cache` folder in `oh_queue/static`. Then rebuild and run.
