import os, re, logging
from sqlalchemy import select, delete
from app.db.database import Session
from app.models.entities import Document, Chunk, Requirement
from app.services.extraction_service import extract, chunks
from app.services.embedding_service import embed_batch

logger=logging.getLogger(__name__)
def process_document(identifier):
    with Session() as db:
        doc=db.get(Document,identifier)
        if not doc: return
        try:
            if db.scalar(select(Chunk).where(Chunk.document_id==doc.id)):
                from app.services.index_service import reindex_document
                reindex_document(identifier)
                return
            doc.status='Extracting'; db.commit()
            pages=extract(doc.path)
            doc.pages=sum(p is not None for p,t in pages)
            doc.status='Chunking'; db.commit()
            content=list(chunks(pages))
            if not content: raise ValueError('No text extracted')
            doc.status='Embedding'; db.commit()
            vectors=embed_batch([text for page,section,text in content])
            for ordinal,(page,section,text) in enumerate(content):
                chunk=Chunk(org_id=doc.org_id,document_id=doc.id,text=text,page=page,section=section,ordinal=ordinal,embedding=vectors[ordinal])
                db.add(chunk); db.flush()
                if doc.kind=='regulatory':
                    from app.services.requirement_extraction_service import candidates
                    for candidate in candidates(text,section):
                        db.add(Requirement(org_id=doc.org_id,document_id=doc.id,chunk_id=chunk.id,**candidate))
            doc.metadata_json={**doc.metadata_json,'embedding_provider':os.getenv('EMBEDDING_PROVIDER','hash-local'),'embedding_model':os.getenv('EMBEDDING_MODEL','sha256-feature-hash-v1'),'extraction_method':'format-aware; PDF OCR fallback','requirement_extraction':'lexical candidates; expert approval required'}
            db.commit()
            if os.getenv('VECTOR_STORE')=='chroma':
                from app.services.vector_store_service import index_document
                index_document(db,doc)
            doc.status='Indexed';doc.error='';db.commit()
        except Exception as exc:
            db.rollback();doc=db.get(Document,identifier);doc.status='Failed';doc.error=str(exc);db.commit();logger.exception('Document processing failed: %s',identifier)
