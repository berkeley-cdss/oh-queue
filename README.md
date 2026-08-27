# Office Hours Queue

## Overview

Provides a web-based interface for requesting help during office hours.

Students request help on an assignment and question number from a location.

This app uses bCourses to manage access, including assigning staff permissions. Courses should set their bCourses ID on [auth](https://auth.apps.cs61a.org) and update it every semester.

## For other courses

This is a hosted app provided by 61A. To set it up for your own course, visit [Auth](https://auth.apps.cs61a.org) and add the desired domain under `Domains`, e.g. `oh.course.org`. Because permissions are assigned with bCourses and not OKPy, you don't need to worry too much about the listed endpoint. You need to contact Silas to ensure that a redirect corresponding to your course's domain is added to the bCourses key. 

## Installation

As of Spring 2026, we are migrating to bCourses authentication (similar to sections) instead of okpyv1. The following instructions have been verified to work on both MAC and Windows, using localhost:3000. We still supply a `Dockerfile.dev` which can be run locally to mimic the production environment.

To use this for local development,

1. Clone the `berkeley-cs61a` repo and open it, but *not* in a Docker container. Note that technically you can do it in the Dev docker container if you wanted to, but Docker isn't a dependency of the Dev container so you would need to install it manually.
2. Duplicate .env.example and copy its contents to a new file, .env. Get your CANVAS_CLIENT_ID and CANVAS_CLIENT_SECRET and add it to the file so bcourses OAUTH can authenticate you in local development. Make sure to gitignore this file.
3. From the root directory `berkeley-cs61a/`, run
   $ docker build --no-cache -f apps/oh/Dockerfile.dev -t oh:dev .
   $ docker run --rm -p 3000:3000 -v "${PWD}:/app" --env-file apps/oh/.env --name oh-dev oh:dev
4. The above terminal runs the Flask server. In another terminal (use split terminal), run the DB migrations
   ```
   docker exec -it oh-dev python manage.py initdb
   docker exec -it oh-dev python manage.py seed_data
   ```
4. The server should now be running on localhost:3000.

### (OUTDATED) Installation (pre-Spring 2026)

As of Fall 2025, the Dev container uses Python 3.10, which is incompatible with several of OH Queue's Python 3.9-based dependencies. Beyond dependency refactoring, the `manage.py` pattern used to interact with the development server is deprecated. Because it would take nontrivial work to wrangle and align all dependency upgrades and migrate to new Flask design patterns, we supply a `Dockerfile.dev` which can be run locally to mimic the production environment.

1. Clone the `berkeley-cs61a` repo and open it, but *not* in a Docker container. Note that technically you can do it in the Dev docker container if you wanted to, but Docker isn't a dependency of the Dev container so you would need to install it manually.
2. From the root directory `berkeley-cs61a/`, run
   ```
   $ docker build --no-cache -f apps/oh/Dockerfile.dev -t oh:dev .
   $ docker run --rm -p 5000:5000 -v "${PWD}:/app" --name oh-dev oh:dev
   $ docker run --rm -p 5000:5000 -v "${PWD}:/app" --env-file apps/oh/.env --name oh-dev oh:dev          
   ```
   * Note that the `docker run` command has only been tested to work in Powershell.
3. This terminal runs the Flask server. In another terminal (use split terminal), run the DB migrations
   ```
   docker exec -it oh-dev python manage.py resetdb
   docker exec -it oh-dev python manage.py seed_data
   docker exec -it oh-dev python manage.py db upgrade
   ```
4. The server should now be running on localhost:5000.

If you ever receive a `FileNotFoundError: ... .webassets-cache/...` error, the static file cache is corrupted, so please delete the `.webassets-cache` folder in `oh/oh_queue/static`. Then rebuild and run.

### (OUTDATED) Installation (pre-Fall 2025)

1. Clone this repo:

   ```
   git clone https://github.com/Cal-CS-61A-Staff/oh-queue.git
   ```

   Then cd into it:

   ```
   cd oh-queue
   ```

2. Create and activate a virtualenv:

   ```
   python3 -m virtualenv env  (If this does not work, try: `virtualenv -p python3 env`)
   source env/bin/activate
   ```

3. Use pip to install all the dependencies:

   ```
   pip install -r requirements.txt
   npm install
   ```

4. Run the database migrations to setup the initial database.

   ```
   ./manage.py resetdb
   ./manage.py seed_data
   ./manage.py db upgrade
   ```

5. Run the server:

   ```
   ./manage.py server
   ```

6. Point your browser to http://localhost:5000. (This might take a while the first time.)

7. You can log in as any email while testing by going to http://localhost:5000/testing-login/.

### Dokku: Initial Deployment

    dokku apps:create app-name
    dokku clone app-name https://github.com/Cal-CS-61A-Staff/oh-queue
    dokku mysql:create db-name
    dokku mysql:link db-name app-name
    dokku domains:set app-name <domain>

    dokku config:set app-name OH_QUEUE_ENV=prod OK_KEY=<OK CLIENT> OK_SECRET=<OK SECRET> SECRET_KEY=<DB SECRET> AUTH_KEY=<AUTH_KEY> AUTH_SECRET=<AUTH_SECRET>
    dokku run app-name ./manage.py db upgrade
    dokku letsencrypt app-name
    # Change OK OAuth to support the domain

For `OK_KEY` and `OK_SECRET`, you'll need to create an Ok OAuth client [here](https://okpy.org/admin/clients) and have it approved by an Ok admin.

### Dokku: Upgrading

    dokku clone app-name https://github.com/Cal-CS-61A-Staff/oh-queue
    dokku run app-name ./manage.py db upgrade
