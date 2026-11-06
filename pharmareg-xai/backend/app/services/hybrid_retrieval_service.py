import os,re
from functools import lru_cache
from sqlalchemy import select
from rank_bm25 import BM25Okapi
from app.models.entities import Chunk, Document
from app.services.embedding_service import embed, cosine, tokens
@lru_cache(maxsize=1)
def reranker():
    from sentence_transformers import CrossEncoder
    kwargs={'local_files_only':os.getenv('MODELS_OFFLINE','false')=='true'}
    if os.getenv('RERANKER_CACHE'):kwargs['cache_folder']=os.environ['RERANKER_CACHE']
    return CrossEncoder(os.getenv('RERANKER_MODEL','cross-encoder/ms-marco-MiniLM-L-6-v2'),**kwargs)

def reference(chunk, doc):
    number=re.match(r'^(\d+(?:\.\d+)*|[IVXLCDM]+|[A-Z])[.)]?\s',chunk.section)
    return {'chunk_id':chunk.id,'document_id':doc.id,'document_version_id':doc.id,'document_title':doc.name,'version':doc.version,'page':chunk.page,'page_reference_type':'PHYSICAL_PDF_POSITION' if chunk.page else 'UNAVAILABLE','section':chunk.section,'section_number':number.group(1) if number else None,'regulatory_dates':doc.metadata_json.get('regulatory_dates',{}),'text':chunk.text,'authority':doc.authority,'jurisdiction':doc.jurisdiction,'source_url':doc.source_url,'checksum':doc.checksum}
def search(db, org_id, query, document_ids=None, kind=None, jurisdiction=None, top_k=8, mode='hybrid'):
    statement = select(Chunk, Document).join(Document, Chunk.document_id==Document.id).where(Chunk.org_id==org_id, Document.archived==0, Document.status=='Indexed')
    if document_ids is not None:
        if not document_ids: return []
        statement = statement.where(Document.id.in_(document_ids))
    if kind: statement=statement.where(Document.kind==kind)
    if jurisdiction: statement=statement.where(Document.jurisdiction==jurisdiction)
    rows = db.execute(statement).all()
    if not rows: return []
    provider=os.getenv('EMBEDDING_PROVIDER','hash-local')
    model=os.getenv('EMBEDDING_MODEL','sha256-feature-hash-v1')
    if any(d.metadata_json.get('embedding_provider',provider)!=provider or d.metadata_json.get('embedding_model',model)!=model for c,d in rows):
        raise ValueError('Selected sources use a different embedding model; rebuild their indexes before searching')
    vector=embed(query)
    dense=[cosine(vector,c.embedding) for c,d in rows]
    if os.getenv('VECTOR_STORE')=='chroma':
        from app.services.vector_store_service import query_vectors
        matches=query_vectors(org_id,vector,[d.id for c,d in rows],len(rows))
        dense=[matches.get(c.id,-1.0) for c,d in rows]
    keyword=BM25Okapi([tokens(c.text) for c,d in rows]).get_scores(tokens(query)).tolist()
    scores=[0.0]*len(rows)
    for values in ([keyword] if mode=='keyword' else [dense] if mode=='dense' else [dense, keyword]):
        for rank,index in enumerate(sorted(range(len(rows)), key=lambda i:values[i], reverse=True)):
            scores[index]+=1/(60+rank+1)
    order=sorted(range(len(rows)),key=lambda i:scores[i],reverse=True)
    if mode=='reranked':
        model=reranker()
        candidates=order[:30]
        reranks=model.predict([(query,rows[i][0].text) for i in candidates])
        order=[i for _,i in sorted(zip(reranks,candidates),reverse=True)]
    result=[]
    for i in order[:top_k]:
        c,d=rows[i]
        result.append({**reference(c,d),'retrieval_score':scores[i],'dense_score':dense[i],'keyword_score':keyword[i]})
    return result
