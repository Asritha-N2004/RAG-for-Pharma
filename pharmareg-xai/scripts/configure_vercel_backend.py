"""Configure only this project's cloud runtime; never print secret values."""
import argparse,json,os,secrets,subprocess
parser=argparse.ArgumentParser();parser.add_argument("--job-mode",choices=["inline","worker"],default="inline");args=parser.parse_args()
from pathlib import Path
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1];workspace=root.parent
cli=workspace/'tools/vercel-cli/node_modules/vercel/dist/vc.js';auth=workspace/'tools/vercel-auth'
credentials=dotenv_values(root/'storage/vercel-deploy/.env.local')
config_path=root/'storage/cloud-runtime.json'
if config_path.exists():values=json.loads(config_path.read_text())
else:
    values={'SECRET_KEY':secrets.token_hex(48),'STORAGE_ENCRYPTION_KEY':secrets.token_hex(32),'AUDIT_HMAC_KEY':secrets.token_hex(48),'SIGNATURE_HMAC_KEY':secrets.token_hex(48)}
    with os.fdopen(os.open(config_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as file:json.dump(values,file)
values.update({'APP_ENV':'production','STORAGE_DIR':'/tmp/pharmareg','ENCRYPT_STORAGE':'true','FILE_STORAGE':'vercel-blob','LLM_PROVIDER':'local-extractive','ALLOW_EXTERNAL_LLM':'false','EMBEDDING_PROVIDER':'hash-local','VECTOR_STORE':'sql','JOB_MODE':args.job_mode,'MAX_UPLOAD_SIZE_MB':'4'})
for name,value in values.items():
    result=subprocess.run(['node',str(cli),'env','add',name,'--environment','production','--project','pharmareg-xai','--scope','resum-projects','--global-config',str(auth),'--force','--yes','--sensitive' if name.endswith('_KEY') else '--no-sensitive'],input=value,text=True,capture_output=True)
    if result.returncode:raise SystemExit('Failed configuring '+name+'; values withheld.')
    print('Configured '+name,flush=True)
env=os.environ.copy();env.update({k:v for k,v in credentials.items() if v is not None});env.update(values);env['STORAGE_DIR']=str(root/'storage/cloud-migration')
result=subprocess.run([str(workspace/'.venv/Scripts/python.exe'),'-m','alembic','upgrade','head'],cwd=root/'backend',env=env,capture_output=True,text=True)
if result.returncode:
    # Migration errors normally contain no credentials, but redact all known secrets defensively.
    error=result.stderr
    for value in list(credentials.values())+list(values.values()):
        if value and len(value)>12:error=error.replace(value,'[redacted]')
    print(error[-4000:]);raise SystemExit('Cloud schema migration failed')
print('Neon schema migrated to head. Runtime secrets remain outside deployment packages.')
