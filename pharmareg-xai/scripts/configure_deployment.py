"""Create deployment secrets once without printing them or changing the active app."""
from pathlib import Path
import argparse,secrets,os
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(root/'deploy'/'.env.deployment'));args=parser.parse_args();path=Path(args.output).resolve();path.parent.mkdir(parents=True,exist_ok=True)
if path.exists():raise SystemExit('Refusing to overwrite existing deployment configuration')
values={'APP_ENV':'production','SECRET_KEY':secrets.token_hex(48),'POSTGRES_PASSWORD':secrets.token_hex(24),'STORAGE_ENCRYPTION_KEY':secrets.token_hex(32),'AUDIT_HMAC_KEY':secrets.token_hex(48),'SIGNATURE_HMAC_KEY':secrets.token_hex(48),'ENCRYPT_STORAGE':'true','LLM_PROVIDER':'local-extractive','ALLOW_EXTERNAL_LLM':'false','FRONTEND_BIND':'127.0.0.1','SITE_ADDRESS':'localhost','INSTALL_ML':'true'}
with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8') as file:
    for key,value in values.items():file.write(key+'='+value+'\n')
print('Created protected deployment configuration:',path)
print('Values were not printed. Configure your real domain, identity provider, SMTP and malware scanner before production acceptance.')
