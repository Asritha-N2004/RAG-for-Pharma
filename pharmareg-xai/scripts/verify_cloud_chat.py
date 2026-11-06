"""Verify actual hosted source-grounded chat without implying neural-model inference."""
import argparse,json,time,uuid
from pathlib import Path
import httpx
parser=argparse.ArgumentParser();parser.add_argument('--url',required=True);args=parser.parse_args()
with httpx.Client(base_url=args.url,timeout=90) as client:
    def call(method,path,**kwargs):
        response=client.request(method,'/api'+path,**kwargs);response.raise_for_status();return response.json()
    account=call('POST','/auth/register',json={'name':'Cloud chat fixture','organization':'DEMONSTRATION cloud chat','email':'cloud-chat-'+uuid.uuid4().hex+'@example.com','password':'Cloud-chat-fixture-password-123'});client.headers['Authorization']='Bearer '+account['access_token']
    doc=call('POST','/documents/upload',files={'file':('DEMONSTRATION-training.txt',b'DEMONSTRATION DATA\nThe Quality Assurance manager retains signed training records. Operators receive training before operating equipment.','text/plain')})
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        state=call('GET','/documents/'+doc['id'])
        if state['status']=='Indexed':break
        assert state['status']!='Failed',state.get('error');time.sleep(1)
    else:raise TimeoutError('Cloud worker did not index chat source')
    session=call('POST','/conversations',json={'title':'DEMONSTRATION controlled cloud chat'});results=[]
    for question in ['Who retains signed training records?','When do operators receive training?']:
        result=call('POST','/conversations/'+session['id']+'/messages',json={'query':question,'document_ids':[doc['id']],'top_k':2})['response'];assert result['evidence'] and result['answer'];results.append({'provider':result['provider'],'evidence_count':len(result['evidence']),'answer':result['answer']})
    assert len(call('GET','/conversations/'+session['id'])['turns'])==2
    output={'passed':True,'url':args.url,'persisted_turns':2,'responses':results,'limitation':'Cloud local-extractive evidence mode; no neural-model accuracy claim.'};path=Path(__file__).resolve().parents[1]/'docs/CLOUD_CHAT_RESULTS.json';path.write_text(json.dumps(output,indent=2),encoding='utf-8');print('Cloud grounded chat and persisted two-turn history passed.')
