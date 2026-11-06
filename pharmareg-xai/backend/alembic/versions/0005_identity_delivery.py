"""Identity controls, attestations, notifications and release validation records."""
from alembic import op
import sqlalchemy as sa
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None
def columns():
    return [sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.String(40),nullable=False),sa.Column('updated_at',sa.String(40),nullable=False),sa.Column('org_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False)]
def upgrade():
    op.create_table('mfa_credentials',*columns(),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),unique=True,nullable=False),sa.Column('encrypted_secret',sa.Text(),nullable=False),sa.Column('enabled',sa.Integer(),nullable=False),sa.Column('last_step',sa.Integer(),nullable=False))
    op.create_table('mfa_recovery_codes',*columns(),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False,index=True),sa.Column('digest',sa.String(64),unique=True,nullable=False),sa.Column('used',sa.Integer(),nullable=False))
    op.create_table('external_identities',*columns(),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False,index=True),sa.Column('issuer',sa.String(500),nullable=False),sa.Column('subject',sa.String(500),nullable=False),sa.UniqueConstraint('issuer','subject'))
    op.create_table('oidc_states',sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.String(40),nullable=False),sa.Column('updated_at',sa.String(40),nullable=False),sa.Column('digest',sa.String(64),unique=True,nullable=False),sa.Column('nonce_digest',sa.String(64),nullable=False),sa.Column('binding_digest',sa.String(64),nullable=False),sa.Column('encrypted_verifier',sa.Text(),nullable=False),sa.Column('expires',sa.Integer(),nullable=False),sa.Column('consumed',sa.Integer(),nullable=False))
    op.create_table('record_signatures',*columns(),sa.Column('target_type',sa.String(30),nullable=False),sa.Column('target_id',sa.String(36),nullable=False,index=True),sa.Column('signer_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('meaning',sa.String(30),nullable=False),sa.Column('statement',sa.Text(),nullable=False),sa.Column('record_hash',sa.String(64),nullable=False),sa.Column('seal',sa.String(64),nullable=False),sa.Column('signer_snapshot',sa.JSON(),nullable=False))
    op.create_table('notifications',*columns(),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False,index=True),sa.Column('event_key',sa.String(200),nullable=False),sa.Column('title',sa.String(250),nullable=False),sa.Column('message',sa.Text(),nullable=False),sa.Column('link',sa.String(250),nullable=False),sa.Column('read_at',sa.String(40)),sa.UniqueConstraint('user_id','event_key'))
    op.create_table('validation_records',*columns(),sa.Column('area',sa.String(100),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('reviewer_id',sa.String(36),sa.ForeignKey('users.id')),sa.Column('statement',sa.Text(),nullable=False),sa.Column('evidence',sa.JSON(),nullable=False))
    for table in ['mfa_credentials','mfa_recovery_codes','external_identities','record_signatures','notifications','validation_records']:op.create_index('ix_'+table+'_org_id',table,['org_id'])
def downgrade():
    for table in ['validation_records','notifications','record_signatures','oidc_states','external_identities','mfa_recovery_codes','mfa_credentials']:op.drop_table(table)
