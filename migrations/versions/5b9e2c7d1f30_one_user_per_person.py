"""One User per person across all offerings, as in seating and sections

Before: a `user` row per person per course (with that course's is_staff, call
and doc links and heartbeat), plus an `account` row per person who has signed
in since the site served every course.
After: one `users` row per person (matched by email, ignoring case), with
their roles in each course as sets of course keys, as in sections. Tickets,
ticket events, group attendance and chat messages are re-pointed at the
merged rows. Heartbeats move to their own table, one per person per course;
the old ones are only seconds old, so they aren't kept.

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
    if any(not row.email for row in rows):
        raise RuntimeError("Some user rows have no email, so they can't be merged; fix them first.")
    for row in rows:
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


def _check_references(bind):
    """Refuse to start if a table this migration doesn't know references users,
    or a reference names a user row that doesn't exist: it has no person to
    point at, and would be lost or stop the migration partway."""
    inspector = sa.inspect(bind)
    unexpected = [
        table for table in inspector.get_table_names()
        if table not in {t for t, _ in USER_REFERENCES} | {"user"}
        and any(fk["referred_table"] == "user" for fk in inspector.get_foreign_keys(table))
    ]
    if unexpected:
        raise RuntimeError(f"Tables {unexpected} reference user; extend this migration to re-point them.")
    dangling = []
    for table, column in USER_REFERENCES:
        ids = [row[0] for row in bind.execute(sa.text(
            f'SELECT DISTINCT {column} FROM "{table}" '
            f'WHERE {column} IS NOT NULL AND {column} NOT IN (SELECT id FROM "user") ORDER BY {column}'
        ))]
        if ids:
            shown = ", ".join(str(i) for i in ids[:10]) + (", ..." if len(ids) > 10 else "")
            dangling.append(f"{table}.{column} (user ids {shown})")
    if dangling:
        raise RuntimeError("Some rows refer to users that don't exist; fix them first: " + "; ".join(dangling))


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
    _check_references(bind)

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

    for person in people.values():
        person["id"] = bind.execute(
            sa.insert(users).returning(users.c.id),
            {
                "email": person["email"], "name": person["name"],
                "canvas_id": person.get("canvas_id"),
                "is_global_admin": person.get("is_global_admin", False),
                "canvas_courses": person.get("canvas_courses") or {},
                "staff_offerings": ",".join(sorted(person["staff"])),
                "admin_offerings": "",
                "student_offerings": ",".join(sorted(person["student"])),
                "call_url": person["call_url"], "doc_url": person["doc_url"],
            },
        ).scalar_one()

    # Map every old per-course row to its person, then re-point references.
    id_map = op.create_table(
        "user_id_map",
        sa.Column("old_id", sa.Integer(), primary_key=True),
        sa.Column("new_id", sa.Integer(), nullable=False),
    )
    mappings = [{"old_id": old_id, "new_id": person["id"]}
                for person in people.values() for old_id in person["old_ids"]]
    if mappings:
        op.bulk_insert(id_map, mappings)

    for table in dict.fromkeys(t for t, _ in USER_REFERENCES):
        _drop_foreign_keys_to(table, "user")
    for table, column in USER_REFERENCES:
        # Two steps, through negative ids, since new ids overlap old ones.
        # "group" is a reserved word, so table names are quoted.
        bind.execute(sa.text(
            f'UPDATE "{table}" SET {column} = '
            f'-(SELECT new_id FROM user_id_map WHERE old_id = "{table}".{column}) '
            f"WHERE {column} IS NOT NULL"
        ))
        bind.execute(sa.text(f'UPDATE "{table}" SET {column} = -{column} WHERE {column} < 0'))
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
