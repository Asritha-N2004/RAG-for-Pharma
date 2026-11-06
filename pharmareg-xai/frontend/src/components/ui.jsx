import React,{useState,useEffect,useRef,useId} from 'react';
import {api,errorMessage} from '../services/api';
export function Badge({children}){return <span className={'badge '+String(children).toLowerCase().replaceAll('_','-')}>{String(children).replaceAll('_',' ')}</span>;}
export function Empty({children='No records yet. Start by uploading source documents.'}){return <div className="empty">{children}</div>;}
export function Panel({title,action,children}){return <section className="panel"><header><h2>{title}</h2>{action}</header>{children}</section>;}
export function Field({label,children}){
 const id=useId();const control=React.isValidElement(children)&&['input','select','textarea'].includes(children.type);
 return <div className="field">{control?<><label className="field-label" htmlFor={children.props.id||id}>{label}</label>{React.cloneElement(children,{id:children.props.id||id,'aria-label':children.props['aria-label']||label})}</>:<><span id={id}>{label}</span><div role="group" aria-labelledby={id}>{children}</div></>}</div>;
}
export function Source({source,onOpen}){
 const [view,setView]=useState(false);
 return <article className="source"><div className="eyebrow">SOURCE EVIDENCE</div><h3>{source.document_title}</h3><p className="muted">Version {source.version} · {source.page?'Page '+source.page:'Page unavailable'} · {source.section||'Section unavailable'}</p><blockquote>{source.text}</blockquote><code>Chunk {source.chunk_id}</code>{source.retrieval_score!=null&&<p className="muted">RRF relevance {source.retrieval_score.toFixed(4)} · not a confidence probability</p>}<div className="row">{source.page&&<button onClick={()=>setView(true)}>View cited page</button>}<button className="link" onClick={()=>onOpen(source)}>Open original document</button></div>{view&&<PageViewer source={source} onClose={()=>setView(false)}/>}</article>;
}
export function PageViewer({source,onClose}){
 const [page,setPage]=useState(source.page);const [url,setUrl]=useState('');const [error,setError]=useState('');const [max,setMax]=useState(source.page);const dialog=useRef(null);
 useEffect(()=>{dialog.current?.showModal();},[]);
 useEffect(()=>{let active=true,u;setUrl('');setError('');const suffix=page===source.page?'?chunk_id='+encodeURIComponent(source.chunk_id):'';
 api.get(`/documents/${source.document_id}/pages/${page}${suffix}`,{responseType:'blob'}).then(r=>{u=URL.createObjectURL(r.data);if(active)setUrl(u);}).catch(async e=>{if(active){if(e.response?.data instanceof Blob){try{setError(JSON.parse(await e.response.data.text()).detail);}catch{setError(errorMessage(e));}}else setError(errorMessage(e));}});
 api.get('/documents/'+source.document_id).then(r=>{if(active)setMax(r.data.pages||source.page);});
 return ()=>{active=false;if(u)URL.revokeObjectURL(u);};},[page,source.document_id,source.chunk_id,source.page]);
 return <dialog className="page-dialog" aria-label={'Source viewer: '+source.document_title} ref={dialog} onClose={onClose}><div className="row"><h2>{source.document_title} · version {source.version}</h2><button aria-label="Close source viewer" onClick={()=>dialog.current.close()}>Close</button></div><div className="row"><button disabled={page<=1} onClick={()=>setPage(page-1)}>Previous page</button><span>Page {page} of {max}</span><button disabled={page>=max} onClick={()=>setPage(page+1)}>Next page</button><a href={`/documents/${source.document_id}?page=${page}&chunk=${source.chunk_id}`}>Source page link</a></div><p className="muted">Highlights match extracted text where the PDF text layer supports exact matches. OCR text and reflowed passages may not highlight.</p>{error?<p role="alert" className="error">{error}</p>:url?<img src={url} alt={`Original source page ${page} with matching passage highlights`}/>:<p role="status">Rendering source page…</p>}</dialog>;
}
