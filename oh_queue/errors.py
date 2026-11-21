"""Error pages that say what went wrong, as in sections, instead of Werkzeug's
bare ones, which leave people with no way back to the site.

Course API calls (paths containing /api/) get JSON with the message; the
course page reloads when its API is refused, to show the page's own error.
"""

import flask
from flask import current_app, jsonify, request
from werkzeug.exceptions import HTTPException


def error_page(title: str, message: str, status: int):
    # Rendered without render_template, whose context processors include
    # Flask-Login's, which loads the signed-in user: that can be what failed
    # (someone not enrolled in the course). error.html doesn't show the user.
    template = current_app.jinja_env.get_template("pages/error.html")
    return template.render(title=title, message=message), status


def register_error_handlers(app: flask.Flask):
    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        if "/api/" in request.path:
            return jsonify({"message": error.description}), error.code
        return error_page(f"{error.code} {error.name}", error.description, error.code)
