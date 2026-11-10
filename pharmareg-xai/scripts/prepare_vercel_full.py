"""Package frontend and actual API sources; all persistent data stays in managed storage."""
from pathlib import Path
import argparse,json,shutil
parser=argparse.ArgumentParser();parser.add_argument("--job-mode",choices=["inline","worker"],default="inline");args=parser.parse_args()
root=Path(__file__).resolve().parents[1];target=root/'storage'/'vercel-full';target.mkdir(parents=True,exist_ok=True)
backend=target/'backend';backend.mkdir(exist_ok=True)
for name in ['app','alembic']:
    shutil.copytree(root/'backend'/name,backend/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copy2(root/'backend'/'alembic.ini',backend/'alembic.ini')
(backend/'requirements.txt').write_text((root/'backend'/'requirements.txt').read_text()+'\nvercel-blob==0.5.1\n',encoding='utf-8')
dependencies=[line.strip() for line in (backend/'requirements.txt').read_text().splitlines() if line.strip() and not line.startswith('#')]
(backend/'pyproject.toml').write_text('[project]\nname="pharmareg-cloud-api"\nversion="1.0.0"\nrequires-python=">=3.12,<3.13"\ndependencies='+json.dumps(dependencies)+'\n',encoding='utf-8')
(backend/'index.py').write_text("import os\nos.environ.setdefault('STORAGE_DIR','/tmp/pharmareg')\nfrom app.main import app\n",encoding='utf-8')
(backend/'Dockerfile.worker').write_text('FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nENV STORAGE_DIR=/tmp/pharmareg\nCMD ["python","-m","app.workers.worker"]\n',encoding='utf-8')
web=target/'web';web.mkdir(exist_ok=True);shutil.copytree(root/'frontend'/'dist',web/'public',dirs_exist_ok=True)
(web/'vercel.json').write_text(json.dumps({'framework':None,'buildCommand':'','outputDirectory':'public','rewrites':[{'source':'/((?!assets(?:/|$)).*)','destination':'/index.html'}]}),encoding='utf-8')
(web/'package.json').write_text('{"name":"pharmareg-web","private":true}',encoding='utf-8')
config={'$schema':'https://openapi.vercel.sh/vercel.json','services':{'web':{'root':'web/','outputDirectory':'public','buildCommand':'echo Static frontend prepared','installCommand':'echo No frontend dependencies required','rewrites':[{'source':'/((?!assets(?:/|$)).*)','destination':'/index.html'}]},'api':{'root':'backend/','entrypoint':'index:app','functions':{'index.py':{'maxDuration':300}}}},'rewrites':[{'source':'/api/(.*)','destination':{'service':'api'}},{'source':'/health','destination':{'service':'api'}},{'source':'/docs','destination':{'service':'api'}},{'source':'/openapi.json','destination':{'service':'api'}},{'source':'/(.*)','destination':{'service':'web'}}],'daemons':{'worker':{'root':'backend/','entrypoint':'Dockerfile.worker','instances':{'iad1':1},'resources':{'requests':{'memory':'1Gi'}}}}}
if args.job_mode=='inline':config.pop('daemons',None)
(target/'vercel.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
(target/'.vercelignore').write_text('.env*\n**/.env*\n**/__pycache__\n**/*.pyc\n',encoding='utf-8')
print('Prepared full cloud package:',target)

print('Processing mode:',args.job_mode,'(set JOB_MODE to match in Vercel)')
