param([int]$Port = 8010,[switch]$LocalAI,[switch]$TLS)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $projectRoot
$pythonPath = Join-Path $workspaceRoot '.venv\Scripts\python.exe'
if ($LocalAI) {
    $pythonPath = Join-Path $workspaceRoot '.venv-ml\Scripts\python.exe'
    $localStorage = Join-Path $projectRoot 'storage\local-ai'
    New-Item -ItemType Directory -Path $localStorage -Force | Out-Null
    $env:STORAGE_DIR = $localStorage
    $env:DATABASE_URL = 'sqlite:///' + (Join-Path $localStorage 'pharmareg.db').Replace('\','/')
    $env:LLM_PROVIDER = 'local-openai'
    $env:LLM_MODEL = 'llama3.2:1b'
    $env:OPENAI_BASE_URL = 'http://localhost:11434/v1'
    $env:LLM_TIMEOUT = '360'
    $env:LLM_MAX_TOKENS = '1200'
    $env:EMBEDDING_PROVIDER = 'sentence-transformers'
    $env:EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
    $env:MODELS_OFFLINE = 'true'
    $env:VECTOR_STORE = 'chroma'
    $env:CHROMA_MODE = 'persistent'
    $env:RERANKER_CACHE = Join-Path $projectRoot 'storage\models'
    $env:JOB_MODE = 'embedded'
}
if (Test-Path -LiteralPath (Join-Path $projectRoot 'storage\tessdata\eng.traineddata')) { $env:TESSDATA_PREFIX = Join-Path $projectRoot 'storage\tessdata' }
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Create the workspace .venv and install backend/requirements.txt first. See README.md.' }
Push-Location (Join-Path $projectRoot 'backend')
try {
    & $pythonPath -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
    if ($TLS) {
        if (!$env:TLS_CERT_FILE -or !$env:TLS_KEY_FILE) {
            if ($env:APP_ENV -eq 'production') { throw 'Production TLS requires TLS_CERT_FILE and TLS_KEY_FILE.' }
            & $pythonPath (Join-Path $projectRoot 'scripts\generate_dev_tls.py')
            $env:TLS_CERT_FILE = Join-Path $projectRoot 'storage\tls\localhost.crt'
            $env:TLS_KEY_FILE = Join-Path $projectRoot 'storage\tls\localhost.key'
        }
        & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port $Port --ssl-certfile $env:TLS_CERT_FILE --ssl-keyfile $env:TLS_KEY_FILE
    } else { & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port $Port }
} finally { Pop-Location }
