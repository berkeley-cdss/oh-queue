from alembic import context
from flask import current_app
from sqlalchemy import text
from logging.config import fileConfig
import logging

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
# Without turning off loggers that already exist, such as the app's when the
# tests run migrations in the same process.
fileConfig(config.config_file_name, disable_existing_loggers=False)
logger = logging.getLogger("alembic.env")


# Flask-SQLAlchemy's engine, which connects the way the app does (on Cloud
# Run, with IAM auth through the Cloud SQL connector rather than a URL).
def get_engine():
    return current_app.extensions["migrate"].db.engine


# For offline mode, which only needs the URL
db_url = get_engine().url.render_as_string(hide_password=False)

# Escape '%' by replacing it with '%%' so Alembic's ConfigParser doesn't trip
if db_url:
    db_url = db_url.replace("%", "%%")

config.set_main_option("sqlalchemy.url", db_url)

target_metadata = current_app.extensions["migrate"].db.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.readthedocs.org/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No changes in schema detected.")

    # Flask-Migrate 4 already sets render_as_batch; a copy, so these callbacks
    # (which read this run's config) aren't kept for the next command run in
    # the same process, such as in the tests
    conf_args = dict(current_app.extensions["migrate"].configure_args)
    conf_args.setdefault("render_as_batch", True)
    conf_args.setdefault("process_revision_directives", process_revision_directives)

    connection = get_engine().connect()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        **conf_args
    )

    try:
        with context.begin_transaction():
            if connection.dialect.name == "postgresql":
                # Several Cloud Run instances can start at once; the first takes
                # this lock and migrates, and the rest wait, then find nothing to do.
                connection.execute(text("SELECT pg_advisory_xact_lock(724502)"))
            context.run_migrations()
    finally:
        connection.close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
