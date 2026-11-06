from typing import Literal
from pydantic import BaseModel, Field, field_validator,model_validator

class Register(BaseModel):
    email: str = Field(min_length=5,max_length=250)
    password: str = Field(min_length=12,max_length=128)
    name: str = Field(min_length=1,max_length=200)
    organization: str = Field(min_length=1,max_length=200)
    @field_validator('email')
    @classmethod
    def email_valid(cls,v):
        if '@' not in v or '.' not in v.split('@')[-1]: raise ValueError('Invalid email')
        return v.strip().lower()
class Login(BaseModel):
    email: str
    password: str
    code: str | None = None
class Refresh(BaseModel):
    refresh_token: str
class Decision(BaseModel):
    decision: Literal['APPROVED','REJECTED','INVESTIGATING','EVIDENCE_REQUESTED','CLOSED']
    explanation: str = Field(min_length=5,max_length=10000)
    classification: Literal['COMPLIANT','PARTIALLY_COMPLIANT','NON_COMPLIANT','NOT_APPLICABLE','INSUFFICIENT_EVIDENCE'] | None = None
    statement: str | None = Field(default=None,max_length=10000)
    designation: Literal['MANDATORY','ADVISORY','CONDITIONAL','UNDETERMINED'] = 'UNDETERMINED'
    applicability: str = Field(default='Reviewed within assessment scope',max_length=5000)
    material_elements: list[str] = Field(default_factory=list,max_length=50)
class AssessmentInput(BaseModel):
    name: str = Field(min_length=1,max_length=250)
    regulatory_document_ids: list[str] = Field(min_length=1,max_length=50)
    organizational_document_ids: list[str] = Field(min_length=1,max_length=100)
    requirement_ids: list[str] = Field(default_factory=list,max_length=1000)
    excluded_requirements: dict[str,str] = Field(default_factory=dict,max_length=1000)
    jurisdiction: str = Field(min_length=1,max_length=100)
    scope: str = Field(min_length=5,max_length=5000)
    @model_validator(mode='after')
    def applicable_scope(self):
        if not self.requirement_ids and not self.excluded_requirements:raise ValueError('Select at least one included or explicitly excluded requirement')
        if set(self.requirement_ids)&set(self.excluded_requirements):raise ValueError('A requirement cannot be both included and excluded')
        if any(not isinstance(r,str) or not 10<=len(r.strip())<=5000 for r in self.excluded_requirements.values()):raise ValueError('Each exclusion needs a 10–5000 character scope rationale')
        return self
class Search(BaseModel):
    query: str = Field(min_length=3,max_length=5000)
    document_ids: list[str] | None = None
    kind: Literal['regulatory','organizational'] | None = None
    jurisdiction: str | None = None
    top_k: int = Field(default=8,ge=1,le=30)
    mode: Literal['keyword','dense','hybrid','reranked'] = 'hybrid'
class CapaInput(BaseModel):
    finding_id: str
    title: str = Field(min_length=3,max_length=250)
    owner: str
    due_date: str
    root_cause: str = ''
    corrective_action: str = ''
    preventive_action: str = ''
class CapaUpdate(BaseModel):
    status: Literal['OPEN','IN_PROGRESS','VERIFICATION','CLOSED']
    implementation_evidence: str = ''
    effectiveness_review: str = ''
class RiskInput(BaseModel):
    finding_id: str
    severity: int = Field(ge=1,le=5)
    likelihood: int = Field(ge=1,le=5)
    detectability: int = Field(ge=1,le=5)
    explanation: str = Field(min_length=5,max_length=5000)
class ReportInput(BaseModel):
    assessment_id: str
    format: Literal['pdf','docx','csv'] = 'pdf'
