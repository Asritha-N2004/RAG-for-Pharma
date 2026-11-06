import os,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.services.source_import_service import fetch
url='https://www.fda.gov/media/71518/download'
name,data,final=fetch(url)
assert data.startswith(b'%PDF-')
import hashlib
result={'official_pinned_https_fetch':True,'source_url':final,'filename':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
(root/'docs'/'SOURCE_IMPORT_RESULTS.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
