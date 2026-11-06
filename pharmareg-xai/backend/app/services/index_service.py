import os
from sqlalchemy import select
from app.db.database import Session
from app.models.entities import Chunk,Document
from app.services.embedding_service import embed_batch
def reindex_document(identifier):
    with Session() as db:
        doc=db.get(Document,identifier)
        chunks=list(db.scalars(select(Chunk).where(Chunk.document_id==identifier).order_by(Chunk.ordinal)))
        if not chunks:raise ValueError('No extracted chunks; retry document extraction instead')
        # UUIDs and content never change, so existing citations remain resolvable.
        vectors=embed_batch([chunk.text for chunk in chunks])
        for chunk,vector in zip(chunks,vectors,strict=True):chunk.embedding=vector
        doc.metadata_json={**doc.metadata_json,'embedding_provider':os.getenv('EMBEDDING_PROVIDER','hash-local'),'embedding_model':os.getenv('EMBEDDING_MODEL','sha256-feature-hash-v1')}
        db.commit()
        if os.getenv('VECTOR_STORE')=='chroma':
            from app.services.vector_store_service import index_document
            index_document(db,doc)
        doc.status='Indexed';doc.error='';db.commit()
