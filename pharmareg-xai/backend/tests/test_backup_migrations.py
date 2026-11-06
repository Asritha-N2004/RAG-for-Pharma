import importlib.util,sqlite3,os,sys,subprocess
from pathlib import Path
import pytest

root=Path(__file__).resolve().parents[2]
def backup_module():
    spec=importlib.util.spec_from_file_location('pharmareg_backup',root/'scripts'/'backup.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def test_encrypted_backup_restore_and_wrong_password(tmp_path):
    backup=backup_module();storage=tmp_path/'storage';storage.mkdir();(storage/'uploads').mkdir();asset=storage/'uploads'/'source.txt';asset.write_text('DEMONSTRATION DATA controlled source')
    with sqlite3.connect(storage/'pharmareg.db') as db:
        db.execute('CREATE TABLE documents (id TEXT,path TEXT)');db.execute('INSERT INTO documents VALUES (?,?)',('id-1',str(asset)))
        db.execute('CREATE TABLE auth_tokens (revoked INTEGER)');db.execute('INSERT INTO auth_tokens VALUES (0)')
    encrypted=tmp_path/'encrypted.backup';password='A-long-backup-password-123'
    result=backup.create(storage,encrypted,password);assert result['members']==2
    assert b'DEMONSTRATION DATA' not in encrypted.read_bytes()
    restored=tmp_path/'restored';backup.restore(encrypted,restored,password)
    assert (restored/'uploads'/'source.txt').read_text()==asset.read_text()
    with sqlite3.connect(restored/'pharmareg.db') as db:
        assert db.execute('SELECT path FROM documents').fetchone()[0]==str(restored/'uploads'/'source.txt')
        assert db.execute('SELECT revoked FROM auth_tokens').fetchone()[0]==1
    with pytest.raises(Exception):backup.restore(encrypted,tmp_path/'wrong-password','incorrect-password')
    assert not (tmp_path/'wrong-password').exists()
    with pytest.raises(ValueError):backup.restore(encrypted,restored,password)
def test_frozen_migrations_fresh_and_upgrade(tmp_path):
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(tmp_path/'migrated.db'),'STORAGE_DIR':str(tmp_path/'state'),'SECRET_KEY':'test-migration-secret-'*3}
    backend=root/'backend'
    for target in ['0002','head']:
        result=subprocess.run([sys.executable,'-m','alembic','upgrade',target],cwd=backend,env=env,capture_output=True,text=True,timeout=45)
        assert result.returncode==0,result.stderr
    with sqlite3.connect(tmp_path/'migrated.db') as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {'document_versions','document_processing_jobs','capa_attachments','evaluation_cases','audit_seals'}<=tables
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0007'
