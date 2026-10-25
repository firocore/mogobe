"""Allow a numeric registration age from 1 through 100."""

import sqlalchemy as sa

from alembic import op

revision = "e266registrationage"
down_revision = "e265minigameexp"
branch_labels = None
depends_on = None


def set_age_range(expression):
    connection = op.get_bind()

    def rebuild():
        with op.batch_alter_table("auth_account") as batch:
            batch.drop_constraint(op.f("ck_auth_account_age_range"), type_="check")
            batch.create_check_constraint(op.f("ck_auth_account_age_range"), expression)

    if connection.dialect.name == "sqlite":
        # Rebuilding the parent must preserve sessions, purchases and other children.
        with op.get_context().autocommit_block():
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            try:
                rebuild()
            finally:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    else:
        rebuild()


def upgrade():
    set_age_range("age BETWEEN 1 AND 100")


def downgrade():
    if op.get_bind().execute(
        sa.text("SELECT 1 FROM auth_account WHERE age NOT BETWEEN 5 AND 14 LIMIT 1")
    ).first():
        raise RuntimeError("Cannot downgrade while accounts with age outside 5 through 14 exist")
    set_age_range("age BETWEEN 5 AND 14")
