"""Configuration, all from environment variables (see .env.example)."""

import os

basedir = os.path.abspath(os.path.dirname(__file__))

# dev or prod. Required, so a deployment that forgets it doesn't get the
# development settings (like the testing login).
ENV = os.getenv("ENV", "").lower()
if ENV not in ("dev", "prod"):
    raise RuntimeError("Set ENV to dev or prod.")


def required(name, dev_default=None):
    """An environment variable that must be set outside development."""
    value = os.getenv(name)
    if value:
        return value
    if ENV == "dev" and dev_default is not None:
        return dev_default
    raise RuntimeError(f"Set {name}.")


DEBUG = ENV == "dev"
SECRET_KEY = required("SECRET_KEY", dev_default="DEV")

if ENV != "dev":
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

SQLALCHEMY_DATABASE_URI = required(
    "DATABASE_URL", dev_default="sqlite:///" + os.path.join(basedir, "app.db")
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
DATABASE_CONNECT_OPTIONS = {}

LOCAL_TIMEZONE = os.getenv("TIMEZONE", "US/Pacific")

CANVAS_SERVER_URL = os.getenv(
    "CANVAS_SERVER_URL", "https://ucberkeleysandbox.instructure.com/"
)
CANVAS_CLIENT_ID = os.getenv("CANVAS_CLIENT_ID")
CANVAS_CLIENT_SECRET = os.getenv("CANVAS_CLIENT_SECRET")
# Optional: members of this Canvas course are staff and admin in every course.
ADMIN_OVERRIDE_CANVAS_COURSE_ID = os.getenv("ADMIN_OVERRIDE_CANVAS_COURSE_ID")
ADMIN_OVERRIDE_CANVAS_COURSE_ID = int(ADMIN_OVERRIDE_CANVAS_COURSE_ID) if ADMIN_OVERRIDE_CANVAS_COURSE_ID else None

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "3000"))

LLM_TIPS_ENDPOINT = os.getenv("LLM_TIPS_ENDPOINT", "")
LLM_TIPS_AUTH_TOKEN = os.getenv("LLM_TIPS_AUTH_TOKEN", "")
