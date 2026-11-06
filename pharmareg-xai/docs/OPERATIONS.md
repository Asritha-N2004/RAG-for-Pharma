# Operations and validation runbook

## Worker and failure recovery

Local `JOB_MODE=embedded` runs a durable SQL queue in the API process. Pending tasks survive restart. `JOB_MODE=worker` separates execution: run `python -m app.workers.worker`. Compose starts that worker and uses Redis wakeups plus SQL polling. Atomic conditional updates claim jobs; a 120-second lease is extended every 20 seconds. Failed tasks back off and retry at most three times. `/api/jobs` and the source/assessment UI expose error history and retry controls. Expired exhausted leases become terminal failures.

Redis notifications carry no source text. Lost notifications do not lose jobs. Configure `REDIS_REQUIRED=true` to fail closed if the distributed rate limiter is unavailable. Embedded mode without Redis retains local rate limits and persistent SQL jobs.

## Model and index changes

Keep the same embedding provider/model for selected sources. Index collections are isolated by organization and embedding configuration fingerprint. After changing a model, rebuild every affected source through its UI or `POST /api/documents/{id}/reindex`. This batches new vectors while preserving source text and chunk UUIDs. Retrieval rejects mixed model provenance; mismatched vector dimensions never silently rank together. Preserve historical original source bytes and finding snapshots.

Use `MODELS_OFFLINE=true` after approved weights are cached. `RERANKER_CACHE` can point to the workspace model cache. Real local inference uses `LLM_PROVIDER=local-openai`, `LLM_MODEL=llama3.2:3b`, `OPENAI_BASE_URL=http://localhost:11434/v1`; no external document transmission occurs. Configure `LLM_TIMEOUT` and `LLM_MAX_TOKENS` for available hardware. Invalid citations/quotes are rejected. A logically inconsistent proposed classification can only be downgraded to insufficient evidence, with the proposal and limitation retained.

For Compose's optional local model service, explicitly set `OPENAI_BASE_URL=http://ollama:11434/v1`. An empty base URL selects the appropriate provider default; OpenAI credentials are not automatically sent to the local Ollama endpoint. After an invalid repair, a clearly labeled rejected-response abstention can be recorded as insufficient evidence so human review can proceed without publishing invalid claims. The smaller installed `llama3.2:1b` completed the final CPU acceptance workflow; choose hardware/model capacity through independent evaluation.

## Official-source import

Administrators register allowlisted HTTPS source URLs. Import revalidates every redirect, rejects credentials/non-443/private DNS addresses, pins the validated public IP for TLS, bounds download size, validates file signatures, and applies the malware-scanner policy. Imported sources remain unverified until a regulatory expert reviews applicability. Download endpoints without file extensions are named using Content-Disposition or a validated PDF signature. An HTTP error is shown to the user, never converted into an invented document.

Official FDA Q7 media URL verified: https://www.fda.gov/media/71518/download . The long legacy `/files/drugs/published/...` URL may fail depending on server request handling. Do not weaken host/IP validation to make an unavailable URL work.

## OCR

PyMuPDF includes the integrated Tesseract OCR engine used here; provide official English `eng.traineddata` and set `TESSDATA_PREFIX` to its directory before startup. `scripts/verify_ocr.py` verifies a synthetic image-only PDF. OCR is a transcription and may be inaccurate; inspect the physical page through the source viewer. Generated highlights require searchable PDF text and are not guaranteed for OCR-only originals.

## Malware scanning and recovery mail

Set `MALWARE_SCANNER_COMMAND` to a JSON argument array, e.g. `["/usr/bin/clamscan","--no-summary"]`. The upload filename is appended as a separate argument; no shell is used. Enable `REQUIRE_MALWARE_SCAN=true` to reject uploads when scanning is unavailable. Scanner nonzero exits/timeouts reject the file and remove the quarantined copy.

Production password recovery uses configured SMTP with STARTTLS and certificate verification: `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, optional `SMTP_USER` and `SMTP_PASSWORD`. Tokens expire in 15 minutes and revoke all sessions when consumed. Development uses a local ignored outbox. The test suite mocks SMTP; no external recovery messages were sent during development.

## Audit integrity and checkpoints

New sensitive events receive HMAC seals chained within each organization. `/api/audit-logs/verify` verifies seals and returns a checkpoint. Keep `AUDIT_HMAC_KEY` in a secrets manager, independently from the database, and export checkpoints to append-only off-host storage. Legacy unsealed events are counted explicitly. This detects modified records and internal deletions but cannot detect an attacker removing a complete trailing suffix plus its seals unless an external checkpoint exists. This is tamper detection, not certified immutable storage or an electronic signature system.

## Backup and restore

Stop writes or enter an operator maintenance window before taking a database+assets backup. The SQLite online backup API provides a consistent database copy; a maintenance window is needed to align file writes and DB references. Install backend requirements, set `BACKUP_ENCRYPTION_PASSWORD` to at least 16 characters, then:

```powershell
python scripts/backup.py create storage D:\Backups\pharmareg.backup
python scripts/backup.py restore D:\Backups\pharmareg.backup D:\Recovery\new-empty-storage
```

Backups use Scrypt-derived AES-256-GCM authenticated encryption and per-file SHA-256 manifests. The tool refuses overwrite and unsafe archive member paths. Do not place the encrypted backup inside the source storage directory. Preserve separately configured environment secrets, audit keys, database credentials, and external checkpoint copies. The development `.secret` is included when present. Model/vector caches can be rebuilt from source and are not included.

For PostgreSQL, use an operator-controlled `pg_dump --format=custom` and `pg_restore` with the matching database release, plus the asset directories and independently managed secrets. Verify restoration on an isolated instance before relying on any backup. Do not point a restored database at production storage.

## Release checks

1. Apply migrations on a fresh isolated database and on a backup of the preceding revision.
2. Run backend tests, frontend tests/build, browser acceptance, and `npm audit`.
3. Run `scripts/verify_real_stack.py` with approved local model weights. Review `docs/REAL_STACK_RESULTS.json` and recorded model limitations. Software fixture labels are not an expert gold standard.
4. Verify OCR, official-source import, backup restore, model version provenance, authorization, queue lease recovery, independent CAPA closure and audit tamper detection.
5. In a Docker-capable environment, run Compose; verify PostgreSQL, Redis, Chroma, API, worker and frontend health, restart recovery, resource limits, backups, TLS termination and least-privilege credentials.
6. Obtain qualified regulatory/domain review, independent annotation, security review, and any required electronic-record validation. Software tests do not certify legal compliance or system suitability under 21 CFR Part 11.

See [enterprise controls](ENTERPRISE_CONTROLS.md) for MFA/SSO, file encryption, TLS, notifications, readiness and executable deployment acceptance.
