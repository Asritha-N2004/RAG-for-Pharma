"""Optional remote Chroma index. SQL is the authoritative rebuild source."""
import os
import hashlib
from sqlalchemy import select
from app.models.entities import Chunk
def client():
    import chromadb
    if os.getenv('CHROMA_MODE')=='persistent':
        from app.core.config import STORAGE
        return chromadb.PersistentClient(path=str(STORAGE/'chroma'))
    return chromadb.HttpClient(host=os.getenv('CHROMA_HOST','localhost'),port=int(os.getenv('CHROMA_PORT','8000')))
def collection_name(org_id):
    fingerprint=hashlib.sha256((os.getenv('EMBEDDING_PROVIDER','hash-local')+':'+os.getenv('EMBEDDING_MODEL','sha256-feature-hash-v1')).encode()).hexdigest()[:12]
    return 'org_'+org_id.replace('-','')+'_'+fingerprint
def index_document(db,doc):
    collection=client().get_or_create_collection(collection_name(doc.org_id),metadata={'hnsw:space':'cosine'})
    rows=list(db.scalars(select(Chunk).where(Chunk.document_id==doc.id)))
    collection.upsert(ids=[c.id for c in rows],embeddings=[c.embedding for c in rows],documents=[c.text for c in rows],metadatas=[{'document_id':doc.id,'version':doc.version,'jurisdiction':doc.jurisdiction,'authority':doc.authority,'page':c.page or 0} for c in rows])
def query_vectors(org_id,vector,document_ids,count):
    collection=client().get_collection(collection_name(org_id))
    if not collection.count():return {}
    response=collection.query(query_embeddings=[vector],n_results=min(count,collection.count()),where={'document_id':{'$in':list(set(document_ids))}})
    return {identifier:1-distance for identifier,distance in zip(response['ids'][0],response['distances'][0])}
