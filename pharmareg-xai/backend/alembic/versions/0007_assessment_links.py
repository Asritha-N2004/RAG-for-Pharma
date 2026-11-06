"""Normalize assessment source and reviewed-requirement configuration."""
import json,uuid
from datetime import datetime,timezone
from alembic import op
import sqlalchemy as sa
revision='0007'
down_revision='0006'
branch_labels=None
depends_on=None
def base():return [sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.String(40),nullable=False),sa.Column('updated_at',sa.String(40),nullable=False),sa.Column('org_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False),sa.Column('assessment_id',sa.String(36),sa.ForeignKey('compliance_assessments.id'),nullable=False)]
def upgrade():
    docs=op.create_table('assessment_documents',*base(),sa.Column('document_id',sa.String(36),sa.ForeignKey('documents.id'),nullable=False),sa.Column('role',sa.String(30),nullable=False),sa.UniqueConstraint('assessment_id','document_id'))
    reqs=op.create_table('assessment_requirements',*base(),sa.Column('requirement_id',sa.String(36),sa.ForeignKey('regulatory_requirements.id'),nullable=False),sa.Column('review_version_id',sa.String(36),sa.ForeignKey('regulatory_requirement_versions.id')),sa.Column('applicability',sa.String(30),nullable=False),sa.Column('rationale',sa.Text(),nullable=False),sa.UniqueConstraint('assessment_id','requirement_id'))
    for name in ['assessment_documents','assessment_requirements']:
        for column in ['org_id','assessment_id']:op.create_index('ix_'+name+'_'+column,name,[column])
    op.create_index('ix_assessment_documents_document_id','assessment_documents',['document_id'])
    connection=op.get_bind();now=datetime.now(timezone.utc).isoformat()
    for row in connection.execute(sa.text('SELECT id,org_id,config FROM compliance_assessments')).mappings():
        config=json.loads(row['config']) if isinstance(row['config'],str) else row['config'];common={'org_id':row['org_id'],'assessment_id':row['id'],'created_at':now,'updated_at':now};seen=set()
        for key,role in [('regulatory_document_ids','REGULATORY'),('organizational_document_ids','ORGANIZATIONAL')]:
            for identifier in config.get(key,[]):
                if identifier in seen:continue
                seen.add(identifier);connection.execute(docs.insert().values(id=str(uuid.uuid4()),document_id=identifier,role=role,**common))
        excluded=config.get('excluded_requirements',{})
        for identifier in dict.fromkeys([*config.get('requirement_ids',[]),*excluded]):
            connection.execute(reqs.insert().values(id=str(uuid.uuid4()),requirement_id=identifier,review_version_id=config.get('requirement_snapshots',{}).get(identifier,{}).get('review_version_id'),applicability='EXCLUDED' if identifier in excluded else 'INCLUDED',rationale=excluded.get(identifier,''),**common))
def downgrade():
    op.drop_table('assessment_requirements');op.drop_table('assessment_documents')
