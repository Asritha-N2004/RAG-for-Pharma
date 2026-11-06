"""Exercise a running deployment over HTTP; never substitutes mocks for services."""
import argparse,json,time,uuid
from pathlib import Path
import httpx

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8080');parser.add_argument('--require-services',action='store_true');parser.add_argument('--ca');parser.add_argument('--output',default='docs/DEPLOYMENT_RESULTS.json');args=parser.parse_args()
    with httpx.Client(base_url=args.url,verify=args.ca or True,timeout=60) as client:
        def call(method,path,**kw):
            response=client.request(method,'/api'+path,**kw);response.raise_for_status();return response
        identity=call('POST','/auth/register',json={'name':'Deployment fixture','organization':'DEMONSTRATION deployment acceptance','email':f'deployment-{uuid.uuid4().hex}@example.com','password':'Deployment-fixture-password-123'}).json();client.headers['Authorization']='Bearer '+identity['access_token']
        readiness=call('GET','/system/readiness').json();checks=readiness['checks'];assert not readiness['service_failures'],readiness
        if args.require_services:
            assert checks['database']['engine']=='postgresql',checks
            assert checks['redis']['status']=='VERIFIED',checks
            assert checks['vector_store']['status']=='VERIFIED' and checks['vector_store']['mode']=='http',checks
        def upload(name,text,kind):
            result=call('POST','/documents/upload',data={'kind':kind,'jurisdiction':'Test','version':'fixture'},files={'file':(name,text.encode(),'text/plain')}).json()
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                doc=call('GET','/documents/'+result['id']).json()
                if doc['status']=='Indexed':return doc
                assert doc['status']!='Failed',doc;time.sleep(1)
            raise TimeoutError('Persistent worker did not index fixture')
        reg=upload('DEMONSTRATION-requirement.txt','DEMONSTRATION DATA - NOT OFFICIAL REGULATION\n1 Training\nPersonnel must receive training before operating equipment.','regulatory')
        sop=upload('DEMONSTRATION-SOP.txt','DEMONSTRATION DATA\n1 Training\nPersonnel receive operator training. QA retains signed completion records.','organizational')
        call('POST','/regulations/'+reg['id']+'/applicability',json={'status':'CURRENT_APPROVED','explanation':'Controlled deployment fixture only; no domain approval.'})
        requirements=call('GET','/regulations/'+reg['id']+'/requirements').json();assert requirements
        for req in requirements:call('POST','/regulations/requirements/'+req['id']+'/review',json={'decision':'APPROVED','explanation':'Controlled deployment fixture review only.','designation':'MANDATORY'})
        assessment=call('POST','/compliance/assessments',json={'name':'DEMONSTRATION deployment workflow','regulatory_document_ids':[reg['id']],'organizational_document_ids':[sop['id']],'requirement_ids':[r['id'] for r in requirements],'scope':'Controlled deployment verification only','jurisdiction':'Test'}).json();aid=assessment['id']
        call('POST','/compliance/assessments/'+aid+'/run');deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            state=call('GET','/compliance/assessments/'+aid).json()
            if state['status']=='COMPLETED':break
            assert state['status']!='FAILED',state;time.sleep(1)
        else:raise TimeoutError('Assessment worker did not complete')
        findings=call('GET','/compliance/assessments/'+aid+'/findings').json();assert findings
        for finding in findings:call('POST','/compliance/findings/'+finding['id']+'/review',json={'decision':'EVIDENCE_REQUESTED','classification':'INSUFFICIENT_EVIDENCE','explanation':'Deployment fixture only; qualified evidence review still required.'})
        formats={}
        for fmt,magic in [('pdf',b'%PDF-'),('docx',b'PK'),('csv',None)]:
            report=call('POST','/reports/generate',json={'assessment_id':aid,'format':fmt}).json();content=call('GET','/reports/'+report['id']+'/download').content;assert content and (magic is None or content.startswith(magic));formats[fmt]=len(content)
        original=call('GET','/documents/'+reg['id']+'/preview').content;assert b'DEMONSTRATION' in original
        output={'passed':True,'url':args.url,'readiness':readiness,'assessment_id':aid,'findings':len(findings),'reports':formats,'notes':'Synthetic workflow fixture; no domain accuracy or certification claim.'};path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(output,indent=2));print('Deployment workflow passed; evidence: '+str(path))
if __name__=='__main__':main()
