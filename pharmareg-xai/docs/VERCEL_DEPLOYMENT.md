# Vercel deployment

## Current runtime

https://pharmareg-xai.vercel.app now hosts the React frontend and real FastAPI backend in the resum-projects/pharmareg-xai project. The app uses request-driven durable job processing (JOB_MODE=inline), without an always-on daemon. The backend-pending notice and 503 placeholder are removed.

An isolated Neon PostgreSQL project uses the existing free-plan integration. New originals, CAPA attachments and reports are AES-GCM encrypted and stored in a private Vercel Blob store; authorization is enforced before authenticated decryption/download. Temporary local files are not the durable storage. Local users, documents and databases were not uploaded or migrated: create a fresh cloud workspace.

Current cloud configuration explicitly uses local-extractive evidence mode, hash development embeddings and SQL vector storage. It does not claim that the laptop's Llama, Sentence Transformer or Chroma processes run in Vercel. Actual local-model verification remains separate. A configured remote inference endpoint and compatible embedding service/runtime are needed to enable neural inference in the cloud. No external LLM transmissions are enabled.

## Deployment and secrets

Run `python scripts/prepare_vercel_full.py --job-mode inline` to package only API source and built public frontend assets into ignored storage/vercel-full. Its Python service declares all requirements in pyproject.toml. The static service declares its public output directory and SPA routing. Runtime credentials come from Vercel environment variables, not uploaded .env files.

`scripts/configure_vercel_backend.py` configures only the PharmaReg project, keeps generated encryption/audit/signing keys in ignored storage/cloud-runtime.json and applies the real Neon schema migration. Preserve these keys separately and never rotate them casually: existing encrypted files and seals depend on them. Provider database/blob credentials come from the linked managed resources. Existing unrelated Vercel projects and databases were left untouched.

Deploy storage/vercel-full with the official Vercel CLI using --prod --scope resum-projects. Verify the worker using `vercel daemons inspect worker`. The old 1 GiB always-on worker stopped after the team exhausted its shared Hobby daemon memory quota on 10 November 2026. The default package now omits daemons and uses the same SQL leases in request-driven mode. Status polling resumes eligible queued/retry/expired-lease jobs, within a 300-second function limit. Jobs that exceed function limits need smaller documents or a suitably hosted worker; no paid plan upgrade was made. To use a dedicated worker again, pass --job-mode worker to both cloud configuration and packaging scripts after arranging adequate capacity.

## Acceptance and limits

- API health and identity endpoints return 200; root and /chat serve the frontend without the pending notice.
- docs/VERCEL_BACKEND_WORKFLOW_RESULTS.json records actual cloud registration, private file processing through the worker, assessment, human review and PDF/DOCX/CSV downloads.
- docs/CLOUD_BLOB_RESULTS.json records an actual private encrypted upload/download round trip after removing the local original.
- Cloud chat persisted two grounded turns. Browser MFA/accessibility and mobile navigation passed. The full browser workflow surfaced a CAPA form loading race and a PostgreSQL audit-lock deadlock; both were fixed. Focused recovery of that same CAPA passed verification, independent closure and PDF download (browser-vercel-capa-results.json). Initial failed browser diagnostics are retained honestly.
- Cloud uploads are capped at 4 MiB to fit the function request boundary; the 50 MB local limit is not advertised as a cloud limit.
- Local real-AI and OCR verification is not proof that those optional runtimes or language data are configured in this cloud deployment.
- Live SMTP, identity provider, antivirus and formal qualified regulatory validation still require deployment-specific configuration.

The older prepare_vercel.py helper is retained for static frontend deployment with an external HTTPS backend. Do not use its no-backend mode to replace the now connected full deployment.

Current production deployment: dpl_J4EDGSJydT7mK9T85cpmcUYunRok. Actual PostgreSQL FK/audit-lock concurrency test passed using FOR NO KEY UPDATE, preserving serialized audit chains without FK lock upgrades.

Request-driven recovery is tenant-scoped and only resumes existing authorized jobs; it does not create new assessments during a status read. In-app notification synchronization still occurs when the inbox is accessed; unattended minute-based reminder scheduling requires a worker.

Verified 10 November 2026: frontend sign-up/MFA/accessibility passed; actual request-driven upload, indexing, assessment, review and all three report downloads passed. The app, API docs and health endpoints share one domain: https://pharmareg-xai.vercel.app , /docs and /health. Current deployment dpl_8bzx8EAnd1fGxNQPoq1eai3YVbFs.
