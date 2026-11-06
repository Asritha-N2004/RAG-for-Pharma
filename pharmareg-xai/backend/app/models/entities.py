import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, Integer, JSON, UniqueConstraint,Index,text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, onupdate=now)
class Organization(Identity, Base):
    __tablename__ = 'organizations'
    name: Mapped[str] = mapped_column(String(200))
class User(Identity, Base):
    __tablename__ = 'users'
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    email: Mapped[str] = mapped_column(String(250), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(50), default='System Administrator')
class Token(Identity, Base):
    __tablename__ = 'auth_tokens'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(20))
    expires: Mapped[int] = mapped_column(Integer)
    revoked: Mapped[int] = mapped_column(Integer, default=0)
class Scoped(Identity):
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
class Document(Scoped, Base):
    __tablename__ = 'documents'
    name: Mapped[str] = mapped_column(String(250))
    category: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    authority: Mapped[str] = mapped_column(String(100), default='User supplied')
    jurisdiction: Mapped[str] = mapped_column(String(100), default='Unspecified')
    version: Mapped[str] = mapped_column(String(100), default='1')
    regulatory_status: Mapped[str] = mapped_column(String(30), default='UNVERIFIED')
    source_url: Mapped[str] = mapped_column(Text, default='')
    checksum: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='Queued')
    error: Mapped[str] = mapped_column(Text, default='')
    pages: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
class Chunk(Scoped, Base):
    __tablename__ = 'document_chunks'
    document_id: Mapped[str] = mapped_column(ForeignKey('documents.id'), index=True)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(String(250), default='')
    ordinal: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list] = mapped_column(JSON)
class Requirement(Scoped, Base):
    __tablename__ = 'regulatory_requirements'
    document_id: Mapped[str] = mapped_column(ForeignKey('documents.id'), index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey('document_chunks.id'))
    original: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='PENDING')
    designation: Mapped[str] = mapped_column(String(30), default='UNDETERMINED')
    applicability: Mapped[str] = mapped_column(Text, default='Requires expert review')
class Assessment(Scoped, Base):
    __tablename__ = 'compliance_assessments'
    name: Mapped[str] = mapped_column(String(250))
    config: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default='DRAFT')
    error: Mapped[str] = mapped_column(Text, default='')
class Finding(Scoped, Base):
    __tablename__ = 'compliance_findings'
    assessment_id: Mapped[str] = mapped_column(ForeignKey('compliance_assessments.id'), index=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey('regulatory_requirements.id'))
    original: Mapped[dict] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(30), default='PENDING')
    reviewed_classification: Mapped[str | None] = mapped_column(String(40), nullable=True)
class Review(Scoped, Base):
    __tablename__ = 'review_decisions'
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    decision: Mapped[str] = mapped_column(String(40))
    explanation: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSON)
class Capa(Scoped, Base):
    __tablename__ = 'capa_records'
    finding_id: Mapped[str] = mapped_column(ForeignKey('compliance_findings.id'))
    title: Mapped[str] = mapped_column(String(250))
    status: Mapped[str] = mapped_column(String(40), default='OPEN')
    data: Mapped[dict] = mapped_column(JSON)
class Report(Scoped, Base):
    __tablename__ = 'generated_reports'
    assessment_id: Mapped[str] = mapped_column(ForeignKey('compliance_assessments.id'))
    format: Mapped[str] = mapped_column(String(10))
    snapshot: Mapped[dict] = mapped_column(JSON)
    path: Mapped[str] = mapped_column(Text, default='')
class Audit(Scoped, Base):
    __tablename__ = 'audit_logs'
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
class Chat(Scoped, Base):
    __tablename__ = 'chat_messages'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    question: Mapped[str] = mapped_column(Text)
    response: Mapped[dict] = mapped_column(JSON)
class Evaluation(Scoped, Base):
    __tablename__ = 'evaluation_runs'
    config: Mapped[dict] = mapped_column(JSON)
    metrics: Mapped[dict] = mapped_column(JSON)
class Setting(Scoped, Base):
    __tablename__ = 'system_settings'
    __table_args__ = (UniqueConstraint('org_id','key'),)
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[dict] = mapped_column(JSON)
class RiskAssessment(Scoped, Base):
    __tablename__ = 'risk_assessments'
    finding_id: Mapped[str] = mapped_column(ForeignKey('compliance_findings.id'),index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    factors: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)

class ProcessingJob(Scoped, Base):
    __tablename__ = 'document_processing_jobs'
    __table_args__=(Index('uq_active_job_target','org_id','target_id',unique=True,sqlite_where=text("state IN ('QUEUED','RUNNING','RETRY')"),postgresql_where=text("state IN ('QUEUED','RUNNING','RETRY')")),)
    task: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str] = mapped_column(String(36),index=True)
    state: Mapped[str] = mapped_column(String(20),default='QUEUED',index=True)
    attempts: Mapped[int] = mapped_column(Integer,default=0)
    max_attempts: Mapped[int] = mapped_column(Integer,default=3)
    available_at: Mapped[int] = mapped_column(Integer,default=0)
    lease_until: Mapped[int] = mapped_column(Integer,default=0)
    lease_token: Mapped[str] = mapped_column(String(64),default='')
    error: Mapped[str] = mapped_column(Text,default='')
    progress: Mapped[dict] = mapped_column(JSON,default=dict)
class DocumentVersion(Scoped, Base):
    __tablename__ = 'document_versions'
    document_id: Mapped[str] = mapped_column(ForeignKey('documents.id'),unique=True)
    family_id: Mapped[str] = mapped_column(String(36),index=True)
    previous_document_id: Mapped[str | None] = mapped_column(ForeignKey('documents.id'),nullable=True)
    publication_date: Mapped[str | None] = mapped_column(String(10),nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(10),nullable=True)
    revision_date: Mapped[str | None] = mapped_column(String(10),nullable=True)
class RequirementVersion(Scoped, Base):
    __tablename__ = 'regulatory_requirement_versions'
    requirement_id: Mapped[str] = mapped_column(ForeignKey('regulatory_requirements.id'),index=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'),nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
class CapaAttachment(Scoped, Base):
    __tablename__ = 'capa_attachments'
    capa_id: Mapped[str] = mapped_column(ForeignKey('capa_records.id'),index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(250))
    path: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64))
class CapaEvent(Scoped, Base):
    __tablename__ = 'capa_events'
    capa_id: Mapped[str] = mapped_column(ForeignKey('capa_records.id'),index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    snapshot: Mapped[dict] = mapped_column(JSON)
class ChatSession(Scoped, Base):
    __tablename__ = 'chat_sessions'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    title: Mapped[str] = mapped_column(String(200))
class ChatTurn(Scoped, Base):
    __tablename__ = 'chat_turns'
    session_id: Mapped[str] = mapped_column(ForeignKey('chat_sessions.id'),index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    question: Mapped[str] = mapped_column(Text)
    response: Mapped[dict] = mapped_column(JSON)
class EvaluationDataset(Scoped, Base):
    __tablename__ = 'evaluation_datasets'
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text,default='')
class EvaluationCase(Scoped, Base):
    __tablename__ = 'evaluation_cases'
    dataset_id: Mapped[str] = mapped_column(ForeignKey('evaluation_datasets.id'),index=True)
    labels: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20),default='PENDING')
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'),nullable=True)
class RegulatorySource(Scoped, Base):
    __tablename__ = 'regulatory_sources'
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(250))
    authority: Mapped[str] = mapped_column(String(100))
    jurisdiction: Mapped[str] = mapped_column(String(100))
    approved_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
class AuditSeal(Scoped, Base):
    __tablename__ = 'audit_seals'
    audit_id: Mapped[str] = mapped_column(ForeignKey('audit_logs.id'),unique=True)
    previous_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64),unique=True)
class MfaCredential(Scoped, Base):
    __tablename__ = 'mfa_credentials'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'),unique=True)
    encrypted_secret: Mapped[str] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(Integer,default=0)
    last_step: Mapped[int] = mapped_column(Integer,default=-1)
class RecoveryCode(Scoped, Base):
    __tablename__ = 'mfa_recovery_codes'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'),index=True)
    digest: Mapped[str] = mapped_column(String(64),unique=True)
    used: Mapped[int] = mapped_column(Integer,default=0)
class ExternalIdentity(Scoped, Base):
    __tablename__ = 'external_identities'
    __table_args__=(UniqueConstraint('issuer','subject'),)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'),index=True)
    issuer: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(500))
class OidcState(Identity, Base):
    __tablename__ = 'oidc_states'
    digest: Mapped[str] = mapped_column(String(64),unique=True)
    nonce_digest: Mapped[str] = mapped_column(String(64))
    binding_digest: Mapped[str] = mapped_column(String(64))
    encrypted_verifier: Mapped[str] = mapped_column(Text)
    expires: Mapped[int] = mapped_column(Integer)
    consumed: Mapped[int] = mapped_column(Integer,default=0)
class RecordSignature(Scoped, Base):
    __tablename__ = 'record_signatures'
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str] = mapped_column(String(36),index=True)
    signer_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    meaning: Mapped[str] = mapped_column(String(30))
    statement: Mapped[str] = mapped_column(Text)
    record_hash: Mapped[str] = mapped_column(String(64))
    seal: Mapped[str] = mapped_column(String(64))
    signer_snapshot: Mapped[dict] = mapped_column(JSON)
class Notification(Scoped, Base):
    __tablename__ = 'notifications'
    __table_args__=(UniqueConstraint('user_id','event_key'),)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'),index=True)
    event_key: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(250))
    message: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(250))
    read_at: Mapped[str | None] = mapped_column(String(40),nullable=True)
class ValidationRecord(Scoped, Base):
    __tablename__ = 'validation_records'
    area: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30),default='PENDING')
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'),nullable=True)
    statement: Mapped[str] = mapped_column(Text,default='')
    evidence: Mapped[dict] = mapped_column(JSON,default=dict)
class EvidenceMapping(Scoped, Base):
    __tablename__ = 'evidence_mappings'
    __table_args__=(UniqueConstraint('finding_id','chunk_id','role'),)
    finding_id: Mapped[str] = mapped_column(ForeignKey('compliance_findings.id'),index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey('document_chunks.id'))
    document_id: Mapped[str] = mapped_column(ForeignKey('documents.id'),index=True)
    role: Mapped[str] = mapped_column(String(40))
    snapshot: Mapped[dict] = mapped_column(JSON)
class AssessmentDocument(Scoped, Base):
    __tablename__ = 'assessment_documents'
    __table_args__=(UniqueConstraint('assessment_id','document_id'),)
    assessment_id: Mapped[str] = mapped_column(ForeignKey('compliance_assessments.id'),index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey('documents.id'),index=True)
    role: Mapped[str] = mapped_column(String(30))
class AssessmentRequirement(Scoped, Base):
    __tablename__ = 'assessment_requirements'
    __table_args__=(UniqueConstraint('assessment_id','requirement_id'),)
    assessment_id: Mapped[str] = mapped_column(ForeignKey('compliance_assessments.id'),index=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey('regulatory_requirements.id'))
    review_version_id: Mapped[str | None] = mapped_column(ForeignKey('regulatory_requirement_versions.id'),nullable=True)
    applicability: Mapped[str] = mapped_column(String(30))
    rationale: Mapped[str] = mapped_column(Text,default='')
