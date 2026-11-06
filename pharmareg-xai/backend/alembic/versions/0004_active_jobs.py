"""Prevent concurrent active jobs from mutating the same source or assessment."""
from alembic import op
import sqlalchemy as sa
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None
def upgrade():
    op.create_index('uq_active_job_target','document_processing_jobs',['org_id','target_id'],unique=True,sqlite_where=sa.text("state IN ('QUEUED','RUNNING','RETRY')"),postgresql_where=sa.text("state IN ('QUEUED','RUNNING','RETRY')"))
def downgrade():op.drop_index('uq_active_job_target',table_name='document_processing_jobs')
