# SPDX-License-Identifier: GPL-2.0-or-later
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

Checklist (MASTERPLAN.md §13.5): backward compatible with the running
revision (expand/contract)? Locks and index strategy? RLS policies, FORCE ROW
LEVEL SECURITY and grants for every new tenant table? Tested downgrade?
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    """Apply the migration."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Revert the migration."""
    ${downgrades if downgrades else "pass"}
