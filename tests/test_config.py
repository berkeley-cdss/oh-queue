"""config.py refuses to start with missing or development settings outside development."""

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PRODUCTION = {
    "ENV": "prod",
    "SECRET_KEY": "secret",
    "DATABASE_URL": "postgresql://db.example.edu/oh",
    "COURSE_KEY": "data8",
    "CANVAS_COURSE_ID": "5",
}


def load_config(env, *values):
    """Import config.py in a new interpreter with only ``env`` set; return
    (exit code, the requested values or the error)."""
    script = "import config; print(repr([getattr(config, name) for name in %r]))" % (values,)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env={"PATH": os.environ["PATH"], **env},
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip().splitlines()[-1]
    return result.returncode, output


@pytest.mark.parametrize("env_value", [None, "", "staging", "production"])
def test_env_must_be_dev_or_prod(env_value):
    env = {} if env_value is None else {"ENV": env_value}
    code, error = load_config(env)
    assert code != 0
    assert "Set ENV to dev or prod." in error


def test_env_is_case_insensitive():
    assert load_config({"ENV": "DEV"}, "ENV") == (0, "['dev']")


def test_development_defaults():
    code, values = load_config({"ENV": "dev"}, "COURSE_KEY", "CANVAS_COURSE_ID", "DEBUG", "SECRET_KEY")
    assert code == 0
    assert values == "['cs61a', 157, True, 'DEV']"


def test_production_starts_with_everything_set():
    code, values = load_config(PRODUCTION, "COURSE_KEY", "CANVAS_COURSE_ID", "DEBUG", "SESSION_COOKIE_SECURE")
    assert code == 0
    assert values == "['data8', 5, False, True]"


@pytest.mark.parametrize("missing", ["SECRET_KEY", "DATABASE_URL", "COURSE_KEY", "CANVAS_COURSE_ID"])
def test_production_requires(missing):
    env = {k: v for k, v in PRODUCTION.items() if k != missing}
    code, error = load_config(env)
    assert code != 0
    assert f"Set {missing}." in error


def test_email_server_needs_a_sender():
    code, error = load_config({"ENV": "dev", "EMAIL_SERVER": "smtp.example.edu"})
    assert code != 0
    assert "Set EMAIL_SENDER" in error


def test_admin_override_course_is_optional():
    assert load_config({"ENV": "dev"}, "ADMIN_OVERRIDE_CANVAS_COURSE_ID") == (0, "[None]")
    assert load_config(
        {"ENV": "dev", "ADMIN_OVERRIDE_CANVAS_COURSE_ID": "42"}, "ADMIN_OVERRIDE_CANVAS_COURSE_ID"
    ) == (0, "[42]")
