"""Authenticated file-envelope encryption; plaintext is materialized only for processing."""
import os,json,secrets,tempfile,mimetypes
from pathlib import Path
from contextlib import contextmanager
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.responses import Response,FileResponse
from urllib.parse import quote
from app.core.config import STORAGE
MAGIC=b'PHARMAREG-FILE-v1\x00'
def enabled():return os.getenv('ENCRYPT_STORAGE','false').lower()=='true'
def key():
    value=os.getenv('STORAGE_ENCRYPTION_KEY','')
    try:parsed=bytes.fromhex(value)
    except ValueError:raise ValueError('STORAGE_ENCRYPTION_KEY must be a 64-character hex key')
    if len(parsed)!=32:raise ValueError('STORAGE_ENCRYPTION_KEY must be a 64-character hex key')
    return parsed
def remote(path):return str(path).startswith('blob:')
def raw_bytes(path):
    if remote(path):
        from vercel.blob import sync as blob
        result=blob.get_blob(str(path)[5:],access='private')
        if result is None:raise FileNotFoundError('Stored file unavailable')
        return result.body
    return Path(path).read_bytes()
def persist(path):
    path=Path(path)
    if os.getenv('FILE_STORAGE','local')!='vercel-blob':return str(path)
    from vercel.blob import sync as blob
    name=path.resolve().relative_to(STORAGE).as_posix()
    uploaded=blob.put_blob(name,path.read_bytes(),access='private',add_random_suffix=False)
    path.unlink()
    return 'blob:'+uploaded.pathname

def read(path):
    raw=raw_bytes(path)
    if not raw.startswith(MAGIC):return raw
    offset=len(MAGIC);size=int.from_bytes(raw[offset:offset+2],'big');metadata=raw[offset+2:offset+2+size];nonce=raw[offset+2+size:offset+14+size]
    return AESGCM(key()).decrypt(nonce,raw[offset+14+size:],MAGIC+metadata)
def encrypt_file(path):
    path=Path(path)
    if not enabled():return persist(path)
    original=path.read_bytes()
    if original.startswith(MAGIC):return persist(path)
    metadata=json.dumps({'extension':path.suffix.lower()},separators=(',',':')).encode();nonce=secrets.token_bytes(12)
    encrypted=MAGIC+len(metadata).to_bytes(2,'big')+metadata+nonce+AESGCM(key()).encrypt(nonce,original,MAGIC+metadata)
    destination=path.with_name(path.name+'.enc');temporary=destination.with_name(destination.name+'.'+secrets.token_hex(8)+'.tmp')
    try:temporary.write_bytes(encrypted);temporary.replace(destination);path.unlink()
    finally:temporary.unlink(missing_ok=True)
    return persist(destination)
@contextmanager
def materialize(path):
    if not remote(path):
        local=Path(path)
        with local.open('rb') as file:encrypted=file.read(len(MAGIC))==MAGIC
        if not encrypted:yield local;return
    folder=STORAGE/'processing';folder.mkdir(parents=True,exist_ok=True)
    name=Path(str(path));extension=Path(name.stem).suffix.lower() if name.suffix.lower()=='.enc' else name.suffix.lower()
    if extension not in {'.pdf','.docx','.txt','.csv','.xlsx'}:raise ValueError('Stored file has an unsupported format')
    with tempfile.TemporaryDirectory(prefix='decrypt-',dir=folder) as work:
        temporary=Path(work)/('source'+extension);temporary.write_bytes(read(path));yield temporary
@contextmanager
def pdf(path):
    import pymupdf
    with materialize(path) as source:
        with pymupdf.open(source) as document:yield document
def download(path,name):
    if not remote(path):
        with Path(path).open('rb') as file:encrypted=file.read(len(MAGIC))==MAGIC
        if not encrypted:return FileResponse(path,filename=name,headers={'X-Content-Type-Options':'nosniff'})
    return Response(read(path),media_type=mimetypes.guess_type(name)[0] or 'application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(name),'X-Content-Type-Options':'nosniff'})
