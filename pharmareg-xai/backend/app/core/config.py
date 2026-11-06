import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / '.env')
STORAGE = Path(os.getenv('STORAGE_DIR', str(ROOT / 'storage'))).resolve()
STORAGE.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{STORAGE / "pharmareg.db"}')
if DATABASE_URL.startswith(('postgres://','postgresql://')):DATABASE_URL='postgresql+psycopg://'+DATABASE_URL.split('://',1)[1]
secret_file = STORAGE / '.secret'
if not os.getenv('SECRET_KEY'):
    if os.getenv('APP_ENV') == 'production':
        raise RuntimeError('SECRET_KEY is required in production')
    if not secret_file.exists():
        import secrets
        secret_file.write_text(secrets.token_hex(48))
SECRET_KEY = os.getenv('SECRET_KEY') or secret_file.read_text()
if len(SECRET_KEY) < 32:
    raise RuntimeError('SECRET_KEY must contain at least 32 characters')
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'local-extractive')
ALLOW_EXTERNAL_LLM = os.getenv('ALLOW_EXTERNAL_LLM', 'false').lower() == 'true'
MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_SIZE_MB', '50')) * 1024 * 1024
if LLM_PROVIDER not in {'local-extractive','openai','local-openai'}:
    raise RuntimeError('Unsupported LLM_PROVIDER')
if LLM_PROVIDER != 'local-extractive' and not os.getenv('LLM_MODEL'):
    raise RuntimeError('LLM_MODEL is required for model-based assessment')
if LLM_PROVIDER == 'openai' and (not ALLOW_EXTERNAL_LLM or not os.getenv('OPENAI_API_KEY')):
    raise RuntimeError('OpenAI requires explicit ALLOW_EXTERNAL_LLM=true and OPENAI_API_KEY')
if os.getenv('EMBEDDING_PROVIDER','hash-local') not in {'hash-local','sentence-transformers'}:
    raise RuntimeError('Unsupported EMBEDDING_PROVIDER')
os.environ.setdefault('ENCRYPT_STORAGE','true' if os.getenv('APP_ENV')=='production' else 'false')
if os.getenv('ENCRYPT_STORAGE','false').lower()=='true':
    try:
        if len(bytes.fromhex(os.getenv('STORAGE_ENCRYPTION_KEY','')))!=32:raise ValueError()
    except ValueError:raise RuntimeError('Encrypted storage requires STORAGE_ENCRYPTION_KEY containing 64 hex characters')
