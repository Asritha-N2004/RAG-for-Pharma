from sqlalchemy import select
from app.db.database import Session
from app.models.entities import Assessment, Requirement, RequirementVersion, Chunk, Document, Finding,ProcessingJob,EvidenceMapping
from app.services.hybrid_retrieval_service import search, reference
from app.services.rag_service import assess
def check_revisions(db,assessment):
    import os
    from app.core.config import LLM_PROVIDER
    config=assessment.config
    if config.get('provider')!=LLM_PROVIDER or ('model' in config and config['model']!=os.getenv('LLM_MODEL','')):raise ValueError('Configured model changed after the draft was saved; create a new assessment with the current configuration')
    for identifier,frozen in config.get('requirement_snapshots',{}).items():
        req=db.get(Requirement,identifier)
        latest=db.scalar(select(RequirementVersion).where(RequirementVersion.requirement_id==identifier).order_by(RequirementVersion.created_at.desc()).limit(1))
        if not req or req.org_id!=assessment.org_id or req.statement!=frozen['statement'] or frozen['review_version_id']!=(latest.id if latest else None):raise ValueError('Requirement review changed after draft creation; edit and save the draft to review the changed requirement')

def run_assessment(identifier):
    with Session() as db:
        assessment=db.get(Assessment,identifier)
        if assessment.status=='COMPLETED':return
        try:
            config=assessment.config
            check_revisions(db,assessment)
            import os
            from app.core.config import LLM_PROVIDER
            if config.get('provider')!=LLM_PROVIDER or ('model' in config and config['model']!=os.getenv('LLM_MODEL','')):raise ValueError('Configured model changed after the draft was saved; create a new assessment with the current configuration')
            requirement_ids=[*config['requirement_ids'],*config.get('excluded_requirements',{})]
            requirements=list(db.scalars(select(Requirement).where(Requirement.org_id==assessment.org_id,Requirement.id.in_(requirement_ids),Requirement.status=='APPROVED')))
            if len(requirements)!=len(requirement_ids): raise ValueError('All selected requirements must remain approved')
            pending=[]
            from app.services.gap_detection_service import screen
            document_gaps={identifier:screen(list(db.scalars(select(Chunk).where(Chunk.document_id==identifier,Chunk.org_id==assessment.org_id)))) for identifier in config['organizational_document_ids']}
            for req in requirements:
                doc=db.get(Document,req.document_id)
                if doc.regulatory_status!='CURRENT_APPROVED' or doc.archived: raise ValueError('Regulatory applicability must remain approved')
                regulatory=reference(db.get(Chunk,req.chunk_id),doc)
                excluded=config.get('excluded_requirements',{}).get(req.id)
                evidence=[] if excluded else search(db,assessment.org_id,req.statement,config['organizational_document_ids'],kind='organizational',top_k=6)
                reviewed=db.scalar(select(RequirementVersion).where(RequirementVersion.requirement_id==req.id).order_by(RequirementVersion.created_at.desc()).limit(1))
                frozen=config.get('requirement_snapshots',{}).get(req.id)
                if frozen and (frozen['statement']!=req.statement or frozen['review_version_id']!=(reviewed.id if reviewed else None)):raise ValueError('Requirement review changed after the draft was saved; update the draft before running')
                elements=frozen['material_elements'] if frozen else reviewed.snapshot.get('material_elements',[req.statement]) if reviewed else [req.statement]
                if excluded:
                    output={'status':'NOT_APPLICABLE','citations':[],'excerpts':[],'element_assessments':[{'element':element,'status':'UNCLEAR','citations':[],'quote':''} for element in elements],'explanation':'Authorized assessment-scope review excluded this requirement: '+excluded,'gaps':[],'contradictions':[],'provider':'human-reviewed scope exclusion; no model inference','validation_status':'DOCUMENTED_SCOPE_REVIEW'}
                else:output=assess(req.statement,evidence,config['scope'],elements)
                # Store immutable source snapshots and model output for reproducibility.
                result={'requirement_text':req.statement,'regulatory_evidence':[regulatory],'organizational_evidence':evidence,'compliance_status':output['status'],'reasoning_summary':output['explanation'],'evidence_gaps':output['gaps'],'contradictions':output['contradictions'],'provider':output['provider'],'citations':output['citations'],'evidence_coverage':None,'evidence_sufficiency':'UNVERIFIED' if output['status']=='INSUFFICIENT_EVIDENCE' else 'MODEL_ASSESSED; HUMAN REVIEW REQUIRED','assessment_confidence':None,'risk_level':'UNASSESSED','recommended_action':'Review source passages and obtain objective records for missing elements.','limitations':['Documentary evidence does not establish operational implementation.','Model scores are not calibrated probabilities.']}
                result['element_assessments']=output['element_assessments'];result['excerpts']=output['excerpts']
                result['model_proposed_status']=output.get('model_proposed_status',output['status']);result['validation_limitations']=output.get('validation_limitations',[])
                result['generation_metadata']=output.get('generation_metadata',{'mode':'local-extractive; no inference'})
                if excluded:result['scope_evidence']={'assessment_id':assessment.id,'scope':config['scope'],'exclusion_reason':excluded,**config['applicability_review']}
                result['validation_status']=output.get('validation_status','VALIDATED_STRUCTURE_AND_QUOTES' if output['provider']!='local-extractive; no LLM inference' else 'NOT_MODEL_ASSESSED')
                result['citation_binding_corrections']=output.get('citation_binding_corrections',[])
                if output.get('provider_proposed_output'):result['provider_proposed_output']=output['provider_proposed_output']
                result['evidence_coverage']=sum(x['status']=='SUPPORTED' for x in output['element_assessments'])/len(elements) if elements else None
                result['coverage_method']='Fraction of reviewed material elements with exact-quote model support; not a probability or independently validated completeness score.'
                result['document_gap_candidates']=document_gaps
                pending.append(Finding(org_id=assessment.org_id,assessment_id=assessment.id,requirement_id=req.id,original=result))
                job=db.scalar(select(ProcessingJob).where(ProcessingJob.target_id==identifier,ProcessingJob.task=='assessment',ProcessingJob.state=='RUNNING'))
                if job:job.progress={'completed_requirements':len(pending),'total_requirements':len(requirements)};db.commit()
            db.add_all(pending);db.flush()
            for finding in pending:
                for key,role in [('regulatory_evidence','REGULATORY_CONTEXT'),('organizational_evidence','ORGANIZATIONAL_CANDIDATE')]:
                    for source in finding.original[key]:db.add(EvidenceMapping(org_id=assessment.org_id,finding_id=finding.id,chunk_id=source['chunk_id'],document_id=source['document_id'],role=role,snapshot=source))
            assessment.status='COMPLETED';db.commit()
        except Exception as exc:
            db.rollback();assessment=db.get(Assessment,identifier);assessment.status='FAILED';assessment.error=str(exc);db.commit()
