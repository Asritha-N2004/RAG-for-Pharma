"""Encrypted research-instance backup. PostgreSQL uses pg_dump + the same asset archive.

The live SQLite database is copied through SQLite's online backup API. Asset inventory
is checksummed; use a maintenance window for a transaction-consistent DB+asset boundary.
Restore writes into a NEW empty destination and verifies every archive member.
"""
import argparse,os,json,io,sqlite3,zipfile,hashlib,secrets
from pathlib import Path,PurePosixPath
from contextlib import closing
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
MAGIC=b'PHARMAREG-BACKUP-v1\x00'
def key(password,salt):return Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(password.encode())
def create(storage,output,password):
    storage=Path(storage).resolve();output=Path(output).resolve()
    if output.is_relative_to(storage):raise ValueError('Store backups outside the runtime storage tree')
    if len(password)<16:raise ValueError('Backup password must have at least 16 characters')
    memory=io.BytesIO();manifest={}
    with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as archive:
        database=storage/'pharmareg.db'
        if not database.exists():raise ValueError('Expected storage/pharmareg.db; use pg_dump and the documented asset procedure for PostgreSQL or a nonstandard database location')
        if database.exists():
            temporary=output.parent/('backup-'+secrets.token_hex(12)+'.sqlite')
            try:
                with closing(sqlite3.connect(database)) as source,closing(sqlite3.connect(temporary)) as destination:source.backup(destination)
                data=temporary.read_bytes();archive.writestr('pharmareg.db',data);manifest['pharmareg.db']=hashlib.sha256(data).hexdigest()
            finally:temporary.unlink(missing_ok=True)
        for path in storage.rglob('*'):
            relative=path.relative_to(storage)
            if not path.is_file() or path.is_symlink() or relative.parts[0] not in {'uploads','reports','capa','.secret'}:continue
            data=path.read_bytes();name=relative.as_posix();archive.writestr(name,data);manifest[name]=hashlib.sha256(data).hexdigest()
        archive.writestr('MANIFEST.json',json.dumps(manifest,sort_keys=True))
        archive.writestr('METADATA.json',json.dumps({'original_storage':str(storage),'format_version':1}))
    salt=os.urandom(16);nonce=os.urandom(12);cipher=AESGCM(key(password,salt)).encrypt(nonce,memory.getvalue(),MAGIC)
    with output.open('xb') as file:file.write(MAGIC+salt+nonce+cipher)
    return {'members':len(manifest),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
def restore(backup,destination,password):
    destination=Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):raise ValueError('Restore destination must be new or empty')
    raw=Path(backup).read_bytes()
    if not raw.startswith(MAGIC):raise ValueError('Unsupported backup')
    offset=len(MAGIC);salt=raw[offset:offset+16];nonce=raw[offset+16:offset+28]
    decoded=AESGCM(key(password,salt)).decrypt(nonce,raw[offset+28:],MAGIC)
    with zipfile.ZipFile(io.BytesIO(decoded)) as archive:
        manifest=json.loads(archive.read('MANIFEST.json'))
        for name,checksum in manifest.items():
            relative=PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:raise ValueError('Unsafe archive member')
            data=archive.read(name)
            if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('Backup checksum mismatch')
        destination.mkdir(parents=True,exist_ok=True)
        for name in manifest:
            path=destination.joinpath(*PurePosixPath(name).parts);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(name))
        metadata=json.loads(archive.read('METADATA.json'));origin=Path(metadata['original_storage'])
    # Rebase authorized asset paths; restored instances must not read the original storage.
    with closing(sqlite3.connect(destination/'pharmareg.db')) as db,db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ['documents','generated_reports','capa_attachments']:
            if table not in tables:continue
            for identifier,path in db.execute(f'SELECT id,path FROM {table}').fetchall():
                if not path:continue
                try:relative=Path(path).relative_to(origin)
                except ValueError:raise ValueError('Backup database references an asset outside its source storage')
                db.execute(f'UPDATE {table} SET path=? WHERE id=?',(str(destination/relative),identifier))
        if 'auth_tokens' in tables:db.execute('UPDATE auth_tokens SET revoked=1')
    return {'restored_members':len(manifest)}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['create','restore']);parser.add_argument('source');parser.add_argument('destination');args=parser.parse_args()
    password=os.environ.get('BACKUP_ENCRYPTION_PASSWORD','')
    if not password:raise SystemExit('Set BACKUP_ENCRYPTION_PASSWORD; passwords are never passed on the command line')
    print(json.dumps(create(args.source,args.destination,password) if args.action=='create' else restore(args.source,args.destination,password),indent=2))
