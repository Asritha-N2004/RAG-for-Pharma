# PharmaReg-XAI

An evidence-grounded pharmaceutical regulatory decision-support application with a React frontend, FastAPI backend, durable jobs, authenticated document processing, hybrid retrieval, model assessment, source inspection, human review, risk/CAPA, reports and research evaluation.

Running real local-AI profile: **http://127.0.0.1:8027** — API docs: **http://127.0.0.1:8027/docs**. Existing extractive workspace: http://127.0.0.1:8010 . Each profile has isolated storage.

See [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md) for exact test results and remaining environment/domain validation. This software does not certify regulatory compliance or replace qualified review.

## Start the existing workspace

From the parent workspace:

```powershell
.\pharmareg-xai\scripts\start.ps1
```

Open http://127.0.0.1:8010 . API docs: http://127.0.0.1:8010/docs . Register a fresh isolated organization; no shared default account is installed. Port 8000 is not modified.

For actual local models, semantic embeddings and persistent Chroma, use the isolated local-AI profile:

```powershell
.\pharmareg-xai\scripts\start.ps1 -LocalAI -Port 8027
```

This uses `.venv-ml`, the installed local Ollama `llama3.2:1b`, cached MiniLM embeddings and a separate `storage/local-ai` database. The verified cross-encoder cache is `storage/models`. Default mode is explicitly local-extractive and conservative; configured model mode is clearly identified in results. Neither mode transmits documents externally by default.

## Fresh installation

Python 3.12 and Node 22+ are supported. From the parent directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r pharmareg-xai\backend\requirements.txt
Copy-Item pharmareg-xai\.env.example pharmareg-xai\.env
cd pharmareg-xai\frontend
npm ci
npm run build
cd ..\..
.\pharmareg-xai\scripts\start.ps1
```

If venv cannot bootstrap pip: `python -m pip --python .\.venv\Scripts\python.exe install -r pharmareg-xai\backend\requirements.txt`.

For ML, create a separate environment and install `backend/requirements-ml.txt`. This workspace's `.venv-ml` uses already installed ML libraries plus isolated application dependencies. For reproducible deployment use the supplied requirements and tested package-version records rather than assuming unrelated global packages exist. Approved weights must be available to Sentence Transformers, the cross-encoder, and Ollama. No remote model-code execution is enabled.

This machine originally lacked npm; a downloaded workspace-only CLI is available at `tools/package/bin/npm-cli.js`. From `frontend`, `node ../../tools/package/bin/npm-cli.js run build` is equivalent. Normal installations should use npm.

## Full workflow

1. Register/login; administrators add members with six role choices. All confidential records are scoped to the organization.
2. Upload regulations and organizational PDF/DOCX/TXT/CSV/XLSX files, singly or through bulk upload. Originals are checksummed and preserved. A configured scanner can reject uploads before processing.
3. Optionally register an official URL as an administrator and import through the controlled HTTPS fetcher. Imported regulatory applicability is never automatically approved.
4. Review source dates/version/jurisdiction/applicability. Approve/edit/reject extracted candidate requirements and define their material elements; original wording and review versions remain stored.
5. Use the assessment wizard to select current approved sources, organizational documents, jurisdiction, scope and approved requirements. Save, edit and resume the draft. Its source/review/model configuration is frozen for reproducibility.
6. Run the durable assessment job. Inspect actual processing state, retry failures, compare source passages and open highlighted physical PDF pages. Review gaps, contradictions, material-element support, uncertainty and any model-validation corrections.
7. Record a qualified human decision without replacing the original generated finding. Calculate internal configurable risk and create a CAPA.
8. Attach implementation evidence, track action history and submit verification. A different reviewer must approve closure with implementation/effectiveness evidence.
9. Generate PDF, DOCX or CSV reports from stored snapshots, including sources, model limitations, reviewer decisions, risk and CAPA evidence. Downloads are authenticated.
10. Create evaluation datasets, author expected source/classification/claim labels, obtain a second reviewer approval, and execute actual retrieval/classification/evidence-quality benchmarks. Fixture labels are never presented as independent expert validation.

## Architecture and persistence

```text
React / Vite / Tailwind / Router / TanStack Query
                         │ authenticated API
                      FastAPI
        ┌────────────────┼──────────────────────┐
     Auth/RBAC       Durable SQL jobs       Source/version review
     JWT/Argon2      leases/retries         PDF/Office/OCR/chunks
        │             Redis wakeups              │
        └──────── SQLAlchemy / PostgreSQL ────────┘
                   (SQLite local profile)
                         │
        semantic vectors + BM25 + rank fusion + cross-encoder
                         │ Chroma, tenant/model collections
            grounded model output + strict source validation
                         │
          immutable findings / human review / risk / CAPA
                         │
             reports / audit seals / research evaluation
```

The default SQL-backed queue survives restarts. `JOB_MODE=embedded` runs its worker locally; `JOB_MODE=worker` separates execution with `python -m app.workers.worker`. Redis coordinates wakeups and distributed limits when configured. SQL remains authoritative if a notification is lost. Active target uniqueness, leases and heartbeat prevent overlapping work; failure history and retry controls are exposed in the UI.

The application stores organizations, users, auth tokens, documents/chunks, normalized document versions, requirement versions, assessments/findings, review decisions, risk, CAPA records/events/attachments, conversations/turns, evaluation datasets/cases/runs, jobs, sources, settings, audit logs and seals. UUIDs, foreign keys, tenant indexes and explicit Alembic revisions are used. Full inventory: [docs/FILE_TREE.txt](docs/FILE_TREE.txt).

```text
pharmareg-xai/
├── backend/app/{api,core,db,models,schemas,services,workers}
├── backend/alembic/versions/0001…0004
├── backend/tests/
├── backend/{requirements.txt,requirements.lock.txt,requirements-ml.txt}
├── backend/{Dockerfile,Dockerfile.chroma}
├── frontend/src/{components,pages,services,App.jsx,main.jsx,styles.css}
├── frontend/e2e/                 # expanded browser acceptance
├── frontend/{package.json,package-lock.json,Dockerfile,nginx.conf}
├── scripts/                     # start, fixtures, real stack/chat/OCR/import, backup
├── sample_data/                 # explicit synthetic files + authentic FDA fixture
├── evaluation_data/             # unreviewed annotation template
├── docs/                        # runbook, verification artifacts, screenshots
├── storage/                     # ignored source files, DB, caches, reports, outbox
├── docker-compose.yml
├── .env.example
└── DEVELOPMENT_STATUS.md
```

## Environment and database

Without `DATABASE_URL`, local storage is `storage/pharmareg.db`; SQLite foreign keys are enabled. PostgreSQL uses `postgresql+psycopg://USER:PASSWORD@HOST:5432/pharmareg`. From `backend`, run `python -m alembic upgrade head`. Startup scripts/Compose run migrations first. Revisions are explicit frozen DDL; release tests verify fresh installation and upgrade from revision 0002.

Production requires a `SECRET_KEY` of at least 32 characters. Development creates a persistent ignored secret if absent. `AUDIT_HMAC_KEY` can independently protect audit seals. Keep all secrets outside source control. `.env.example` includes provider, queue, OCR, SMTP, scanning and source-import options.

Access tokens expire after 30 minutes; refresh tokens rotate and are digested/revocable. The browser renews expired access sessions and clears both credentials on failure/logout. Password recovery uses a local development outbox or configured production SMTP with STARTTLS. No external email was sent during tests.

## Models, sources and assessment safeguards

`EMBEDDING_PROVIDER=sentence-transformers` selects pretrained embeddings; `hash-local` is explicitly a deterministic development baseline. Set `EMBEDDING_MODEL`, `RERANKER_MODEL`, optional `RERANKER_CACHE`, and `MODELS_OFFLINE` as needed. `VECTOR_STORE=chroma` uses either `CHROMA_MODE=persistent` or configured `CHROMA_HOST`/`CHROMA_PORT`. Rebuild changed model indexes through the source UI; chunk IDs and source bytes remain unchanged. Mixed embedding provenance is rejected.

For local inference set `LLM_PROVIDER=local-openai`, `OPENAI_BASE_URL=http://localhost:11434/v1`, and an installed `LLM_MODEL`. External OpenAI assessment additionally requires explicit `ALLOW_EXTERNAL_LLM=true` and `OPENAI_API_KEY`. Retrieved text is untrusted data, never executable instructions.

Output schemas bound fields and constrain IDs/quote choices. Exact quotations are checked against actual retrieved text. Misassigned passage references can be rebound only from a verbatim source match; corrections and original provider output are preserved. Invented IDs or text remain rejected and uncited. One repair attempt is allowed; an invalid repaired response produces an explicit REJECTED_REQUIRES_REVIEW abstention with insufficient evidence, not a supported compliance claim. The original rejected proposal and validation limitations remain available to authorized reviewers. Network/service failures remain retryable job failures. Inconsistent classification/element judgments or a violation rationale based on absent documentation can only be withheld as insufficient evidence with the model proposal retained. These are conservative safeguards, not a semantic entailment proof or calibrated probability.

Every finding remains subject to qualified review. Evidence coverage counts material elements with quoted support; it is not retrieval similarity or a statistically calibrated confidence. Office page numbers are null. PDF references are physical 1-based page positions, not automatically printed page labels. OCR/highlighting requires review; source structure detection is heuristic.

## Docker deployment

In the project `.env`, set secure `SECRET_KEY` and `POSTGRES_PASSWORD` (hex passwords avoid URL-encoding ambiguity), then:

```sh
docker compose up --build
```

Open http://localhost:8080 and http://localhost:8080/docs . Services include frontend/Nginx, API, durable worker, PostgreSQL, Redis and Chroma with persistent volumes and health checks. ML-enabled backend builds are controlled by `INSTALL_ML`; default Compose enables the requested semantic/Chroma stack. Optional local Ollama service uses the `local-ai` profile; provision approved model weights separately and configure the provider. The API/worker share source/model storage; internal databases are not exposed on host ports.

Docker/PostgreSQL/live Redis are unavailable on this workstation, so container integration is not claimed as executed. See [docs/OPERATIONS.md](docs/OPERATIONS.md) for deployment acceptance, queue recovery, reindexing, SMTP/scanning, audit checkpoints, encrypted backup/restore and formal validation steps.

## Testing and actual results

```sh
# backend directory
python -m pytest -q --basetemp=../storage/pytest --junitxml=../docs/backend-tests.xml
# frontend directory
npm test
npm run build
npx playwright install chromium
npm run test:e2e
npm audit
```

Browser tests use `APP_URL` (default http://127.0.0.1:8010) and optionally `CHROMIUM_EXECUTABLE`. They include authentic PDF ingestion, candidate approval, SOP processing, draft editing, evidence/page inspection, review, risk, attachment upload, second-user closure, download and mobile navigation. Test organizations and organizational records are explicitly synthetic; automated accounts do not constitute qualified regulatory approval.

Additional actual verification scripts (run from the parent workspace) are `scripts/verify_real_stack.py`, `scripts/verify_real_chat.py`, `scripts/verify_ocr.py` and `scripts/verify_source_import.py`. JSON evidence is written to `docs/`. The authentic FDA source is https://www.fda.gov/media/71518/download . Synthetic fixtures are never labeled official. To regenerate synthetic source files, run `scripts/generate_samples.py`.

Independent annotation is required for research claims. Implemented metrics include retrieval scores/latency, per-class classification metrics and confusion matrices, and labeled evidence/claim quality. Unannotated faithfulness/coverage values remain unmeasured rather than invented. Exact run results and known model failures are in DEVELOPMENT_STATUS.md.

## Troubleshooting and boundaries

- Missing tables: run migrations with the same environment and storage as the server.
- No eligible source: confirm indexing, expert applicability, approved requirements and exact jurisdiction selection.
- Index/model mismatch: reindex all selected source versions using the active embedding configuration.
- Invalid model response: inspect the job error and quoted evidence; retry or use a better configured model. A small local model is not validated regulatory expertise.
- Slow CPU inference: avoid simultaneous model runs, bound output tokens and tune timeout/resources. Jobs preserve retries and failures.
- OCR unavailable: set `TESSDATA_PREFIX` to approved language data; use `verify_ocr.py` for actual image-only extraction.
- Audit integrity: export checkpoints off-host; HMAC seals alone cannot detect deletion of a complete trailing suffix plus all seals.
- Pagination: `/api/records/{collection}` supplies total/limit/offset and filters. Legacy list endpoints remain compatible and capped.
- Production credentials/infrastructure and independent domain review are not supplied by this repository. No automatic emails, scheduled reminders or external publishing were performed during development.

## Completed enterprise controls

MFA, OIDC SSO, signed review attestations, notification scheduling, encrypted file storage, HTTPS deployment, exclusion rationale, normalized evidence links, advanced filters/grouping and paginated collection pages are implemented. See [enterprise controls](docs/ENTERPRISE_CONTROLS.md) for configuration and validation boundaries. The [development status](DEVELOPMENT_STATUS.md) records executed verification separately from external production acceptance.

Cloud application: https://pharmareg-xai.vercel.app — real API, isolated PostgreSQL, private encrypted file storage and durable worker are connected. Create a new cloud workspace; local accounts remain local. The cloud currently uses explicit extractive evidence mode, with a 4 MiB upload cap. See the Vercel deployment documentation for configuration and capacity limits.
