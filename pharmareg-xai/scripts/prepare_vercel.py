"""Package only public frontend assets for Vercel, optionally routing a hosted API."""
import argparse,ipaddress,json,shutil
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]

def prepare(origin=None):
    if origin:
        url=urlsplit(origin)
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in {'','/'}:
            raise ValueError('Backend origin must be a public HTTPS origin without credentials or path')
        if url.hostname.lower()=='localhost' or url.hostname.lower().endswith(('.localhost','.local','.internal')):raise ValueError('Local backend addresses cannot serve Vercel')
        try:
            if not ipaddress.ip_address(url.hostname).is_global:raise ValueError('Private backend addresses cannot serve Vercel')
        except ValueError as exc:
            if str(exc)=='Private backend addresses cannot serve Vercel':raise
        origin=origin.rstrip('/')
    source=ROOT/'frontend'/'dist'
    if not (source/'index.html').is_file():raise FileNotFoundError('Build frontend first with npm run build')
    destination=ROOT/'storage'/'vercel-deploy';destination.mkdir(parents=True,exist_ok=True)
    # Copy public assets only. Storage, databases, keys, model caches and source evidence are never packaged.
    shutil.copytree(source,destination/'public',dirs_exist_ok=True)
    config={'$schema':'https://openapi.vercel.sh/vercel.json','version':2,'framework':None,'buildCommand':'','outputDirectory':'public','rewrites':[],'headers':[{'source':'/(.*)','headers':[{'key':'X-Content-Type-Options','value':'nosniff'},{'key':'X-Frame-Options','value':'DENY'},{'key':'Referrer-Policy','value':'same-origin'}]}]}
    if origin:
        config['rewrites']=[{'source':'/api/:path*','destination':origin+'/api/:path*'},{'source':'/health','destination':origin+'/health'}]
        stale=destination/'api'/'backend-unavailable.mjs';stale.unlink(missing_ok=True)
    else:
        api=destination/'api';api.mkdir(exist_ok=True)
        (api/'backend-unavailable.mjs').write_text("export default function handler(req,res){res.setHeader('Cache-Control','no-store');return res.status(503).json({detail:'Cloud backend connection pending. Sign-in, uploads, chat and assessments are unavailable until a hosted PharmaReg API is connected.'});}\n",encoding='utf-8')
        config['rewrites']=[{'source':'/api/:path*','destination':'/api/backend-unavailable'},{'source':'/health','destination':'/api/backend-unavailable'}]
        index=destination/'public'/'index.html'
        text=index.read_text(encoding='utf-8');notice='<div role="status" style="padding:14px 22px;background:#fff4dd;color:#664409;border-bottom:1px solid #c99d49;font:14px/1.5 system-ui"><strong>Cloud backend connection pending.</strong> This frontend is deployed. Sign-in, uploads, chat and assessments become available after the hosted backend is connected.</div>'
        index.write_text(text.replace('<body>','<body>'+notice),encoding='utf-8')
    config['rewrites'].append({'source':'/((?!api(?:/|$)|assets(?:/|$)|health$).*)','destination':'/index.html'})
    (destination/'vercel.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    (destination/'package.json').write_text(json.dumps({'name':'pharmareg-xai-deployment','private':True,'type':'module','engines':{'node':'24.x'}})+'\n',encoding='utf-8')
    (destination/'.vercelignore').write_text('.vercel\n.env*\n',encoding='utf-8')
    print('Prepared public-only deployment:',destination)
    print('Backend: '+(origin or 'NOT CONNECTED; explicit 503 and visible notice enabled'))
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--backend-origin');args=parser.parse_args();prepare(args.backend_origin)
