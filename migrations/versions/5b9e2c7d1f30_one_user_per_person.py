"""One User per person across all offerings, as in seating and sections

Before: a `user` row per person per course (with that course's is_staff, call
and doc links and heartbeat), plus an `account` row per person who has signed
in since the site served every course.
After: one `users` row per person (matched by email, ignoring case), with
their roles in each course as sets of course keys, as in sections. Each
person keeps the id of their oldest row, so only references to their other
rows (tickets, ticket events, group attendance, chat messages) change:
staging has 2 million ticket events. Rows that refer to a user row that no
longer exists get a placeholder person under that id ("Unknown user <id>"),
so their history stays. Heartbeats move to their own table, one per person
per course; the old ones are only seconds old, so they aren't kept.

Adapted from sections' 0002_single_user.

Revision ID: 5b9e2c7d1f30
Revises: 42b35af5ed41
Create Date: 2026-11-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "5b9e2c7d1f30"
down_revision = "42b35af5ed41"
branch_labels = None
depends_on = None

# Tables with a foreign key to the old `user` table, and the columns holding it.
USER_REFERENCES = [
    ("ticket", "user_id"),
    ("ticket", "helper_id"),
    ("ticket_event", "user_id"),
    ("group_attendance", "user_id"),
    ("chat_message", "user_id"),
]
# Gives SQLite's unnamed foreign keys a name, so batch mode can drop them.
FK_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def _people(bind):
    """One dict per person, merged by email, from the old user and account rows."""
    meta = sa.MetaData()
    old_user = sa.Table("user", meta, autoload_with=bind)
    people = {}
    rows = bind.execute(sa.select(old_user).order_by(old_user.c.id)).all()
    # A row without an email can't be matched to anyone. With nothing pointing
    # at it, it holds nothing to keep (staging has one, a staff row from 2020).
    blank = [row.id for row in rows if not (row.email or "").strip()]
    referenced = [
        f"{table}.{column}" for table, column in USER_REFERENCES
        if blank and bind.execute(sa.text(f'SELECT 1 FROM "{table}" WHERE {column} IN :ids LIMIT 1')
                                  .bindparams(sa.bindparam("ids", expanding=True)), {"ids": blank}).first()
    ]
    if referenced:
        raise RuntimeError(f"User rows {blank} have no email, so they can't be merged, and {', '.join(referenced)} "
                           "refer to some of them; fix them first.")
    for row in rows:
        if row.id in blank:
            continue
        person = people.setdefault(row.email.lower(), {
            "email": row.email, "name": row.name or row.email, "canvas_id": None,
            "is_global_admin": False, "canvas_courses": {},
            "staff": set(), "student": set(), "call_url": None, "doc_url": None, "old_ids": [],
        })
        person["old_ids"].append(row.id)
        # Rows are in id order, so the newest name and links win.
        if row.name:
            person["name"] = row.name
        if row.call_url:
            person["call_url"] = row.call_url
        if row.doc_url:
            person["doc_url"] = row.doc_url
        if row.is_staff:
            person["staff"].add(row.course)
        else:
            person["student"].add(row.course)

    # d3a7e5f1c0b2 made this table, so every database here has it.
    account = sa.Table("account", meta, autoload_with=bind)
    conflicts = []
    for row in bind.execute(sa.select(account).order_by(account.c.id)):
        person = people.setdefault(row.email.lower(), {
            "email": row.email, "name": row.name, "staff": set(), "student": set(),
            "call_url": None, "doc_url": None, "old_ids": [],
        })
        if person.get("canvas_id") not in (None, row.canvas_id):
            # Two bCourses accounts with one email: keeping either would lock the other out.
            conflicts.append(f"{row.email} (Canvas users {person['canvas_id']} and {row.canvas_id})")
        # Signed-in people get their Canvas name and details.
        person.update(name=row.name, canvas_id=row.canvas_id,
                      is_global_admin=bool(row.is_global_admin),
                      canvas_courses=row.canvas_courses or {})
    if conflicts:
        raise RuntimeError("Some emails belong to more than one bCourses account, so they can't be merged; "
                           "fix them first: " + ", ".join(conflicts))
    for person in people.values():
        # Staff in a course where an older row had them as a student.
        person["student"] -= person["staff"]
    return people


def _check_tables(bind):
    """Refuse to start if a table this migration doesn't know references users."""
    inspector = sa.inspect(bind)
    unexpected = [
        table for table in inspector.get_table_names()
        if table not in {t for t, _ in USER_REFERENCES} | {"user"}
        and any(fk["referred_table"] == "user" for fk in inspector.get_foreign_keys(table))
    ]
    if unexpected:
        raise RuntimeError(f"Tables {unexpected} reference user; extend this migration to re-point them.")


def _missing_user_ids(bind):
    """Ids that rows refer to but no user row has. On staging, 34 cs161 tickets
    from 2020-22 belong to one; its foreign key was added without checking."""
    missing = set()
    for table, column in USER_REFERENCES:
        missing |= {row[0] for row in bind.execute(sa.text(
            f'SELECT DISTINCT t.{column} FROM "{table}" t LEFT JOIN "user" u ON u.id = t.{column} '
            f"WHERE t.{column} IS NOT NULL AND u.id IS NULL"
        ))}
    return sorted(missing)


def _insert_in_batches(bind, table, rows, size=500):
    """Insert ``rows`` with one multi-row INSERT per ``size`` of them: the driver
    sends an executemany as one round trip per row."""
    for start in range(0, len(rows), size):
        bind.execute(sa.insert(table).values(rows[start:start + size]))


def _drop_foreign_keys_to(table, referred):
    fks = [fk for fk in sa.inspect(op.get_bind()).get_foreign_keys(table)
           if fk["referred_table"] == referred]
    if not fks:
        return
    with op.batch_alter_table(table, naming_convention=FK_NAMING) as batch:
        for fk in fks:
            name = fk["name"] or f"fk_{table}_{fk['constrained_columns'][0]}_{referred}"
            batch.drop_constraint(name, type_="foreignkey")


def upgrade():
    bind = op.get_bind()
    # Everything that can refuse the data, before anything changes.
    people = _people(bind)
    _check_tables(bind)
    missing = _missing_user_ids(bind)

    users = op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("canvas_id", sa.String(length=255), nullable=True),
        sa.Column("is_global_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("canvas_courses", sa.JSON(), nullable=False),
        sa.Column("staff_offerings", sa.Text(), nullable=False, server_default=""),
        sa.Column("admin_offerings", sa.Text(), nullable=False, server_default=""),
        sa.Column("student_offerings", sa.Text(), nullable=False, server_default=""),
        sa.Column("call_url", sa.String(length=255), nullable=True),
        sa.Column("doc_url", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_canvas_id", "users", ["canvas_id"], unique=True)

    # Each person keeps their oldest row's id (rows were read in id order), and
    # a placeholder keeps the missing id, so most references stay as they are.
    # People who have only signed in get ids after every old one.
    next_id = max([old_id for person in people.values() for old_id in person["old_ids"]] + missing + [0]) + 1
    for person in people.values():
        if person["old_ids"]:
            person["id"] = person["old_ids"][0]
        else:
            person["id"], next_id = next_id, next_id + 1
    for missing_id in missing:
        people[f"missing {missing_id}"] = {
            "id": missing_id, "email": f"unknown-user-{missing_id}@oh-queue.invalid",
            "name": f"Unknown user {missing_id}", "staff": set(), "student": set(),
            "call_url": None, "doc_url": None, "old_ids": [],
        }
    # The rows go in a few statements rather than one each: staging has tens
    # of thousands of people.
    rows = []
    for person in people.values():
        rows.append({
            "id": person["id"], "email": person["email"], "name": person["name"],
            "canvas_id": person.get("canvas_id"),
            "is_global_admin": person.get("is_global_admin", False),
            "canvas_courses": person.get("canvas_courses") or {},
            "staff_offerings": ",".join(sorted(person["staff"])),
            "admin_offerings": "",
            "student_offerings": ",".join(sorted(person["student"])),
            "call_url": person["call_url"], "doc_url": person["doc_url"],
        })
    _insert_in_batches(bind, users, rows)
    if bind.dialect.name == "postgresql":
        # New people get ids after the merged ones.
        bind.execute(sa.text(
            "SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) "
            "FROM users"
        ))

    # Map each person's other rows to them, then re-point references to those.
    id_map = op.create_table(
        "user_id_map",
        sa.Column("old_id", sa.Integer(), primary_key=True),
        sa.Column("new_id", sa.Integer(), nullable=False),
    )
    _insert_in_batches(bind, id_map, [{"old_id": old_id, "new_id": person["id"]}
                                      for person in people.values() for old_id in person["old_ids"]
                                      if old_id != person["id"]])

    for table in dict.fromkeys(t for t, _ in USER_REFERENCES):
        _drop_foreign_keys_to(table, "user")
    for table, column in USER_REFERENCES:
        # Every new id is some person's kept id, never one being mapped away, so
        # one pass is enough. "group" is a reserved word, so names are quoted.
        bind.execute(sa.text(
            f'UPDATE "{table}" SET {column} = user_id_map.new_id FROM user_id_map '
            f'WHERE "{table}".{column} = user_id_map.old_id'
        ))
    for table in dict.fromkeys(t for t, _ in USER_REFERENCES):
        with op.batch_alter_table(table) as batch:
            for referencing_table, column in USER_REFERENCES:
                if referencing_table == table:
                    batch.create_foreign_key(f"fk_{table}_{column}_users", "users", [column], ["id"])
    op.drop_table("user_id_map")

    op.create_table(
        "heartbeat",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course", sa.String(length=255), nullable=False),
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_heartbeat_user_id_users"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course", name="uq_heartbeat_user_id_course"),
    )
    op.create_index("ix_heartbeat_user_id", "heartbeat", ["user_id"])
    op.create_index("ix_heartbeat_course", "heartbeat", ["course"])
    op.create_index("ix_heartbeat_time", "heartbeat", ["time"])

    op.drop_table("account")
    op.drop_table("user")


def downgrade():
    # Per-course rows can't be recovered once merged.
    raise NotImplementedError("Merging users into one row per person can't be undone.")
