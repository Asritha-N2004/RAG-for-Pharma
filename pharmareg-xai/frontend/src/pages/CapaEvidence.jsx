import React,{useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,download} from '../services/api';
import {Field,Badge} from '../components/ui';
export default function CapaEvidence({capa,act}){
 const {data:files=[]}=useQuery({queryKey:['/capa/'+capa.id+'/attachments'],queryFn:async()=>(await api.get('/capa/'+capa.id+'/attachments')).data});const {data:events=[]}=useQuery({queryKey:['/capa/'+capa.id+'/history'],queryFn:async()=>(await api.get('/capa/'+capa.id+'/history')).data});const [history,setHistory]=useState(false);
 return <div><h3>Implementation evidence attachments</h3>{files.map(f=><p key={f.id}><button className="link" onClick={()=>act(()=>download('/capa/attachments/'+f.id+'/download',f.name))}>{f.name}</button><small>SHA256 {f.checksum}</small></p>)}{capa.status!=='CLOSED'&&<form onSubmit={e=>{e.preventDefault();act(()=>api.post('/capa/'+capa.id+'/attachments',new FormData(e.target)));}}><Field label="Attach CAPA evidence"><input type="file" name="file" required accept=".pdf,.docx,.txt,.csv,.xlsx"/></Field><button>Upload evidence attachment</button></form>}<p className="muted">Closure must be approved by a reviewer other than the person who submitted verification.</p><button className="link" onClick={()=>setHistory(!history)}>Show action history ({events.length})</button>{history&&events.map(e=><div key={e.id}><small>{e.created_at} · {e.actor_id}</small><pre className="code-input">{JSON.stringify(e.snapshot,null,2)}</pre></div>)}</div>;
}
