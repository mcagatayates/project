"""make failure_records candidate nullable, add concept_id

Revision ID: f2dbde17231f
Revises: a4d6beb7b0b4
Create Date: 2026-08-14 19:01:15.301488

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.models.base

# revision identifiers, used by Alembic.
revision: str = 'f2dbde17231f'
down_revision: Union[str, None] = 'a4d6beb7b0b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table so this also works on SQLite (used by the test
    # suite), which cannot ALTER COLUMN / add a named FK in place.
    with op.batch_alter_table('failure_records', schema=None) as batch_op:
        batch_op.add_column(sa.Column('concept_id', app.db.models.base.GUID(), nullable=True))
        batch_op.alter_column(
            'generation_candidate_id',
            existing_type=app.db.models.base.GUID(),
            nullable=True,
        )
        batch_op.create_index(
            batch_op.f('ix_failure_records_concept_id'), ['concept_id'], unique=False
        )
        batch_op.create_foreign_key(
            'fk_failure_records_concept_id_concepts', 'concepts', ['concept_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('failure_records', schema=None) as batch_op:
        batch_op.drop_constraint('fk_failure_records_concept_id_concepts', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_failure_records_concept_id'))
        batch_op.alter_column(
            'generation_candidate_id',
            existing_type=app.db.models.base.GUID(),
            nullable=False,
        )
        batch_op.drop_column('concept_id')
