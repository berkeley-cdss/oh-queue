from functools import wraps

from flask import Flask


def job(app: Flask, endpoint):
    """Run the decorated function on a POST to ``/jobs/<endpoint>``, for a
    scheduler to call."""

    def decorator(func):
        @wraps(func)
        def wrapped():
            func()
            return ""

        app.add_url_rule(
            f"/jobs/{endpoint}",
            func.__name__ + "_job",
            wrapped,
            strict_slashes=False,
            methods=["POST"],
        )

        return func

    return decorator
