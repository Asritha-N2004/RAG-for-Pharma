"""Normalize immutable finding-to-source mappings, including existing records."""
import uuid,json
from datetime import datetime,timezone
from alembic import op
import sqlalchemy as sa
revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None
def upgrade():
    table=op.create_table('evidence_mappings',sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.String(40),nullable=False),sa.Column('updated_at',sa.String(40),nullable=False),sa.Column('org_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False),sa.Column('finding_id',sa.String(36),sa.ForeignKey('compliance_findings.id'),nullable=False),sa.Column('chunk_id',sa.String(36),sa.ForeignKey('document_chunks.id'),nullable=False),sa.Column('document_id',sa.String(36),sa.ForeignKey('documents.id'),nullable=False),sa.Column('role',sa.String(40),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),sa.UniqueConstraint('finding_id','chunk_id','role'))
    for column in ['org_id','finding_id','document_id']:op.create_index('ix_evidence_mappings_'+column,'evidence_mappings',[column])
    connection=op.get_bind();now=datetime.now(timezone.utc).isoformat()
    for row in connection.execute(sa.text('SELECT id,org_id,original FROM compliance_findings')).mappings():
        original=json.loads(row['original']) if isinstance(row['original'],str) else row['original']
        seen=set()
        for key,role in [('regulatory_evidence','REGULATORY_CONTEXT'),('organizational_evidence','ORGANIZATIONAL_CANDIDATE')]:
            for evidence in original.get(key,[]):
                pair=(evidence['chunk_id'],role)
                if pair in seen:continue
                seen.add(pair)
                connection.execute(table.insert().values(id=str(uuid.uuid4()),org_id=row['org_id'],finding_id=row['id'],chunk_id=evidence['chunk_id'],document_id=evidence['document_id'],role=role,snapshot=evidence,created_at=now,updated_at=now))
def downgrade():op.drop_table('evidence_mappings')
