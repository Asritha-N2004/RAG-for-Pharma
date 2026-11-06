import csv, io, json
from pathlib import Path
from xml.sax.saxutils import escape
from app.core.config import STORAGE

def generate(report):
    folder=STORAGE/'reports';folder.mkdir(exist_ok=True)
    path=folder/(report.id+'.'+report.format)
    snap=report.snapshot
    from collections import Counter
    distribution=dict(Counter(f['reviewed_classification'] or f['original']['compliance_status'] for f in snap['findings']))
    latest_risk={r['finding_id']:r['factors'] for r in snap.get('risk_assessments',[])}
    if report.format=='csv':
        with path.open('w',newline='',encoding='utf-8-sig') as file:
            writer=csv.writer(file)
            writer.writerow(['Assessment','Finding','Requirement','AI/local status','Human status','Review','Explanation','Regulatory evidence','Organizational evidence','Gaps','Risk'])
            for f in snap['findings']:
                data=f['original']
                row=[snap['assessment']['name'],f['id'],data['requirement_text'],data['compliance_status'],f['reviewed_classification'],f['review_status'],data['reasoning_summary'],json.dumps(data['regulatory_evidence']),json.dumps(data['organizational_evidence']),json.dumps(data['evidence_gaps']),json.dumps(latest_risk.get(f['id'],{}))]
                writer.writerow([("'"+str(v)) if str(v).startswith(('=','+','-','@','\t','\r')) else v for v in row])
    else:
        sections=[('PharmaReg-XAI • Compliance review', 'Decision support; final determination requires qualified human review.\nOrganization: '+snap.get('organization',{}).get('name','Not recorded')+'\nGenerated: '+report.created_at+'\nAssessment ID: '+report.assessment_id),('Executive summary',json.dumps({'findings':len(snap['findings']),'distribution':distribution,'pending_reviews':sum(f['review_status']=='PENDING' for f in snap['findings']),'open_capas':sum(c['status']!='CLOSED' for c in snap['capas'])},indent=2)),('Assessment',json.dumps(snap['assessment'],ensure_ascii=False,indent=2)),('Sources and scope',json.dumps(snap['documents'],ensure_ascii=False,indent=2))]
        for f in snap['findings']:
            data=f['original']
            sections.append(('Finding '+f['id'], f"Requirement: {data['requirement_text']}\nAI/local assessment: {data['compliance_status']}\nProvider: {data['provider']}\nHuman classification: {f['reviewed_classification'] or 'Not reviewed'}\nReview: {f['review_status']}\nExplanation: {data['reasoning_summary']}\nGaps: {json.dumps(data['evidence_gaps'])}\nUncertainty: {json.dumps(data['limitations'])}"))
            for e in data['regulatory_evidence']+data['organizational_evidence']:
                sections.append(('Source excerpt',f"{e['document_title']} | version {e['version']} | page {e['page'] if e['page'] else 'not available'} | section {e['section']}\nDocument {e['document_id']} | chunk {e['chunk_id']} | SHA256 {e['checksum']}\n{e['text']}"))
            sections.append(('Material-element coverage and validation',json.dumps({'model_proposed_status':data.get('model_proposed_status'),'published_status':data['compliance_status'],'element_assessments':data.get('element_assessments',[]),'coverage_method':data.get('coverage_method'),'validation_limitations':data.get('validation_limitations',[]),'generation_metadata':data.get('generation_metadata',{})},indent=2)))
        sections += [('Risk assessments — internal methodology',json.dumps(snap.get('risk_assessments',[]),indent=2)),('Reviewer decisions',json.dumps(snap['reviews'],indent=2)),('Corrective actions',json.dumps(snap['capas'],indent=2)),('CAPA evidence attachment manifest',json.dumps(snap.get('capa_attachments',[]),indent=2)),('Limitations','Local extractive findings are unverified. Retrieval relevance is not evidence coverage. Risk uses an internal assessment methodology. Uploaded regulatory status is expert reviewed, not independently certified.')]
        if report.format=='docx':
            from docx import Document
            doc=Document()
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            footer=doc.sections[0].footer.paragraphs[0];footer.add_run('PharmaReg-XAI | '+report.id+' | Page ')
            field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
            for title,text in sections:
                doc.add_heading(title,level=1);doc.add_paragraph(text)
            doc.save(path)
        else:
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            styles=getSampleStyleSheet();story=[]
            for title,text in sections:
                story += [Paragraph(escape(title),styles['Heading2'])]
                for line in text.splitlines(): story.append(Paragraph(escape(line),styles['BodyText']))
                story.append(Spacer(1,12))
            def footer(canvas,doc):
                canvas.drawString(36,24,f'PharmaReg-XAI | {report.id} | Page {doc.page}')
            SimpleDocTemplate(str(path),rightMargin=36,leftMargin=36).build(story,onFirstPage=footer,onLaterPages=footer)
    from app.services.storage_service import encrypt_file
    report.path=encrypt_file(path)
