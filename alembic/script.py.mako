"""
Alembic Migration File Template (Mako Template)

This Mako template is used to generate new migration files when you run `alembic revision`
or `alembic revision --autogenerate`. Each time you create a migration, Alembic renders
this template and substitutes the placeholders with actual values.

Template variables (populated by Alembic):
- ${message}: Migration description/message
- ${up_revision}: Current revision ID (unique identifier for this migration)
- ${down_revision}: Parent revision ID (the migration this builds upon)
- ${create_date}: Timestamp when migration was created
- ${upgrades}: Auto-generated upgrade operations (e.g., op.create_table, op.add_column)
- ${downgrades}: Auto-generated downgrade operations to reverse the upgrade
- ${imports}: Additional SQLAlchemy imports needed for column types
- ${branch_labels}: For branched migration histories
- ${depends_on}: For migration dependencies

You can customize this template to:
- Add custom imports to all migrations
- Include standard boilerplate code in upgrade()/downgrade() functions
- Modify the migration file structure or documentation format
- Add team-specific patterns or validation logic
"""

"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
${upgrades if upgrades else "    pass"}


def downgrade() -> None:
${downgrades if downgrades else "    pass"}

