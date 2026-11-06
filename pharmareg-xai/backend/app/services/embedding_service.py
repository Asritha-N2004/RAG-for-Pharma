import hashlib, math, os, re
from functools import lru_cache

def tokens(text): return re.findall(r'\b[a-z][a-z0-9]+\b',text.lower())
@lru_cache(maxsize=1)
def sentence_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(os.getenv('EMBEDDING_MODEL','all-MiniLM-L6-v2'),local_files_only=os.getenv('MODELS_OFFLINE','false')=='true')
def embed(text):
    if os.getenv('EMBEDDING_PROVIDER','hash-local') == 'sentence-transformers':
        return sentence_model().encode(text, normalize_embeddings=True).tolist()
    # Explicit development baseline: deterministic feature hashing, not a semantic model.
    vector = [0.0]*256
    for token in tokens(text):
        h = hashlib.sha256(token.encode()).digest()
        vector[int.from_bytes(h[:4],'little')%256] += 1 if h[4]%2 else -1
    norm = math.sqrt(sum(x*x for x in vector)) or 1
    return [x/norm for x in vector]
def embed_batch(texts):
    if os.getenv('EMBEDDING_PROVIDER','hash-local')=='sentence-transformers':
        return sentence_model().encode(texts,batch_size=int(os.getenv('EMBEDDING_BATCH_SIZE','32')),normalize_embeddings=True,show_progress_bar=False).tolist()
    return [embed(text) for text in texts]
def cosine(a,b):
    if len(a)!=len(b): raise ValueError('Embedding dimension mismatch: rebuild the index')
    return sum(x*y for x,y in zip(a,b))
