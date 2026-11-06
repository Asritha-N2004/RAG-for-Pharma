from sqlalchemy import delete
from app.models.entities import AssessmentDocument,AssessmentRequirement
def sync_links(db,assessment):
    db.execute(delete(AssessmentDocument).where(AssessmentDocument.assessment_id==assessment.id,AssessmentDocument.org_id==assessment.org_id));db.execute(delete(AssessmentRequirement).where(AssessmentRequirement.assessment_id==assessment.id,AssessmentRequirement.org_id==assessment.org_id))
    config=assessment.config
    for key,role in [('regulatory_document_ids','REGULATORY'),('organizational_document_ids','ORGANIZATIONAL')]:
        for identifier in dict.fromkeys(config[key]):db.add(AssessmentDocument(org_id=assessment.org_id,assessment_id=assessment.id,document_id=identifier,role=role))
    excluded=config.get('excluded_requirements',{})
    for identifier in [*config['requirement_ids'],*excluded]:db.add(AssessmentRequirement(org_id=assessment.org_id,assessment_id=assessment.id,requirement_id=identifier,review_version_id=config.get('requirement_snapshots',{}).get(identifier,{}).get('review_version_id'),applicability='EXCLUDED' if identifier in excluded else 'INCLUDED',rationale=excluded.get(identifier,'')))
