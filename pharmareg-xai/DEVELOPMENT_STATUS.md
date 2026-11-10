# Development status - 6 November 2026

## Delivery

The application backlog from this continuation is implemented beyond the research baseline. This is evidence-grounded decision support requiring qualified review, not a certified regulatory decision system. External infrastructure acceptance and independently qualified model evaluation remain distinct from software implementation.

Running real local-AI app: http://127.0.0.1:8027 ; API documentation: http://127.0.0.1:8027/docs . Register an organization to begin. The separate extractive profile is http://127.0.0.1:8010 . Other applications on ports 8000/8011 were left unchanged.

## Completed modules

- Authentication, organizations and roles: Argon2/JWT, refresh/revoke/reset/profile/member management, tenant isolation, browser token renewal, TOTP enrollment/replay protection/one-use recovery codes/session rotation, OIDC code/PKCE/nonce/signature/subject-link validation and retained MFA.
- Document lifecycle: PDF/DOCX/TXT/CSV/XLSX, bulk uploads, checksums, malware adapter, original/version/lineage/date/department metadata, archive/search, controlled official HTTPS importer, physical PDF pages and actual image-only OCR.
- Requirements: source-grounded candidates, expert applicability/designation/material-element review, immutable approved versions and preserved elements during editing.
- Retrieval: hash development mode or actual sentence-transformer embeddings, batches/model provenance, SQL or tenant/model-isolated Chroma, BM25/dense/RRF and actual cross-encoder reranking; UUID-stable reindex.
- Assessments: five-step saved/editable drafts, frozen source/review/model configuration, applicability rationale, explicit per-requirement exclusions and reviewer identity. Exclusions create source-linked NOT_APPLICABLE findings pending human review.
- Explainability: structured five-status findings, material-element coverage, quoted evidence, provenance, validation/repair, preserved model proposals, gaps/contradictions, conservative missing-evidence guards and rejected-output abstention; authenticated highlighted PDF pages and original downloads.
- Durable jobs: SQL atomic leased claims, retry/backoff/heartbeat/expired-lease recovery, active-target uniqueness, embedded or standalone worker, optional Redis coordination and fail-closed distributed API rate limits.
- Human review/risk/CAPA: retained original output, reviewer history, configurable internal risk factors, action plans/dates, protected evidence attachments, independent evidenced closure.
- Reports/chat/evaluation: immutable PDF/DOCX/CSV snapshots and downloads; private grounded multi-turn chat; independently approved annotation datasets, retrieval/classification/explainability metrics without fabricated expert labels.
- Enterprise records: explicit consent/meaning and password/MFA reauthentication; HMAC hash-bound finding/CAPA/report attestations, tamper and subsequent-change detection. Formal electronic-record certification is not implied.
- Notifications: private inbox/read states/preferences, daily deduplicated due/overdue CAPA reminders, review and failed-job events, minute worker synchronization.
- Analytics and navigation: server search/filter/date pagination across core collection pages and evaluation history; full filtered risk/department/document/status grouping counts; paginated assessment source choices.
- Security/operations: HMAC-chained audit integrity, encrypted verified backup/restore, AES-GCM new source/attachment/report file encryption, authenticated decrypting processing/downloads, trusted-certificate local HTTPS, Caddy deployment overlay, generated deployment secrets, SMTP STARTTLS and scanner adapters, readiness and operator validation records.
- Persistence/deployment: frozen DDL and additive migrations through 0007, normalized assessment/evidence links with existing-record backfill; Compose PostgreSQL/Redis/Chroma/API/worker/frontend, real-service HTTP acceptance and restart CI.

## Tests executed and results

| Check | Recorded result |
|---|---|
| Backend regression, migrations, isolation, concurrency, queue, backup, security and enterprise controls | 51 passed, 0 failed; docs/backend-tests.xml |
| Frontend component/session tests | 6 passed, 0 failed; docs/frontend-tests.json |
| Production frontend build | Passed |
| Browser workflow, attestation, independent CAPA closure, mobile navigation, MFA/recovery and accessibility | 3 passed, 0 failed; docs/browser-results.json |
| Automated WCAG 2A/AA and 2.1A/AA rules on 11 pages | No violations on tested pages; comprehensive human audit remains required |
| Certificate-verified local HTTPS with encrypted sources, processing, assessment, review and all three report downloads | Passed; docs/HTTPS_ENCRYPTED_RESULTS.json |
| Python locked-dependency and npm audits | Zero known reported vulnerabilities; docs/python-audit.json and docs/npm-audit.json |
| Actual real Llama, semantic embeddings and persistent Chroma browser profile | 3 passed, 0 failed; docs/browser-real-ai-results.json; full workflow approximately 3 minutes |
| Real cross-encoder/384-dimensional embeddings/authentic FDA PDF assessment and CAPA/report workflow | Passed; docs/REAL_STACK_RESULTS.json (58 physical pages, 176 chunks) |
| Real grounded local-model chat | Two validated turns; docs/REAL_CHAT_RESULTS.json |
| Real scanned-image OCR and pinned official FDA import | Passed; docs/OCR_RESULTS.json and docs/SOURCE_IMPORT_RESULTS.json |
| Docker/PostgreSQL/Redis runtime | Not executed here: Docker/WSL and database/cache servers are unavailable; runnable CI and acceptance script provided |
| Live SMTP, antivirus and identity provider | Adapters/fixture failure and security tests passed; external credentials/engines not supplied |

The browser workflow uses an authentic FDA regulatory PDF and explicitly synthetic organizational data: registration, extraction/indexing, candidate approval, SOP upload, draft save/edit/resume, model assessment, cited page inspection, human decision/attestation, risk, evidence attachment, independent CAPA closure, report download and mobile navigation.

## Known limitations and external acceptance

1. Small local models made real errors: paraphrased/misattributed quotes, omitted elements, unsupported violation proposals and CPU timeouts. Invalid claims are rejected or conservatively withheld; guarded insufficient-evidence output is not a claim of validated model accuracy. Original proposals and corrections remain reviewable.
2. Provide independently qualified labels and reviewers before making research accuracy/faithfulness or operational suitability claims. Software fixture accounts are not experts.
3. Run Docker deployment/restart acceptance on a Docker-capable host. The CI uses actual PostgreSQL/Redis/Chroma and deterministic extraction/embeddings for service integration; actual neural-model verification is separate.
4. Configure real SSO, SMTP, antivirus, public TLS/domain, secrets management, database/volume encryption and external append-only audit checkpoints. File encryption covers new originals, attachments and reports; existing plaintext assets and extracted database passages require operator migration/infrastructure controls.
5. Obtain formal regulatory/security/accessibility/electronic-record validation as applicable. The release validation page records evidence and qualification; it does not certify itself.
6. Heading/requirement extraction is heuristic; OCR can mistranscribe. Office pagination needs a controlled external renderer if rendered page numbers are required. PDF highlights depend on its text layer.

No known failing application regression remains in the executed local suite. Current dependency deprecation warnings are non-fatal. The previously pending MFA/SSO, attestations, notification scheduling, exclusion rationale and advanced pagination/grouping are implemented.

## Next operator tasks

Run the deployment acceptance on the target host, configure external services, collect independently approved domain labels and record qualified acceptance evidence. See README.md, docs/OPERATIONS.md, docs/ENTERPRISE_CONTROLS.md and docs/FILE_TREE.txt for setup, commands, controls and full source structure. Original requirements are preserved in docs/MASTER_REQUIREMENTS.txt. No secrets are committed.

## Vercel deployment - 6 November 2026

- Created `resum-projects/pharmareg-xai` and deployed the sanitized frontend at https://pharmareg-xai.vercel.app . Vercel deployment: dpl_DDEhwE8A2HiFrNGsZYKK2xst7CN9, READY.
- Verified root and /chat return 200 and show the explicit backend-pending notice. /health and API return explicit 503 JSON while no backend is configured. See docs/VERCEL_RESULTS.json and docs/vercel-deployment.png.
- This is frontend deployment only. Full cloud workflow is not yet available: the API, database/files, durable worker and actual inference are still local. A hosted HTTPS backend origin is required; the user has been asked for it or a backend hosting choice.
- Added scripts/prepare_vercel.py for public-only packaging and same-origin API/health rewrites once the backend origin is supplied. No local documents, databases, secret keys or model weights were uploaded.
- See docs/VERCEL_DEPLOYMENT.md for the concrete follow-up deployment command and acceptance checks.

## Connected Vercel backend - supersedes the frontend-only entry

The real FastAPI API, isolated Neon PostgreSQL, private encrypted Vercel Blob storage and a ready durable worker daemon are deployed at https://pharmareg-xai.vercel.app . Current deployment dpl_FeLHYZeu1t3M22W7J6vugzzgr6LY. Root, /chat and /health return 200 and the pending notice is removed. Cloud registration, upload/worker processing, assessment/review and all three report downloads passed (docs/VERCEL_BACKEND_WORKFLOW_RESULTS.json). Actual encrypted private Blob roundtrip passed after local-file removal. Backend regression: 51 passed plus the new cloud-storage test passed. Cloud browser and persisted-chat acceptance are running. Cloud inference is explicitly local-extractive/hash evidence mode, not the laptop's Llama/semantic models. No existing local private accounts or records were migrated. Cloud requests cap uploads at 4 MiB; free-plan quotas apply. See docs/VERCEL_DEPLOYMENT.md.

The final Vercel package also prevents CAPA submission before cloud finding options are loaded. Production deployment: dpl_8mCHTLa5yhgwmq6shtKWyNJAE23T. The earlier cloud browser timeout is retained as a diagnosed loading-race regression; final browser rerun follows the fix. Two persisted source-grounded cloud chat turns passed in explicit local-extractive mode (docs/CLOUD_CHAT_RESULTS.json).

Cloud browser testing additionally reproduced a real PostgreSQL audit deadlock during CAPA verification: concurrent child inserts held FK KEY SHARE locks, then audit FOR UPDATE upgrades conflicted. Audit chain serialization now uses PostgreSQL FOR NO KEY UPDATE, preserving mutual exclusion while allowing those FK locks. A real two-transaction Neon concurrency regression passed with a valid chained audit (docs/POSTGRES_AUDIT_RESULTS.json). The corrected production deployment is dpl_J4EDGSJydT7mK9T85cpmcUYunRok. Eleven targeted audit/workflow/storage tests passed after the fix. Focused browser acceptance resumes the same previously created CAPA through verification, independent closure and report download; results are recorded separately without relabeling the earlier failed run as passed.

Final connected-cloud acceptance: focused browser recovery passed in 58.6 seconds, completing the same authentic-FDA-PDF assessment workflow through CAPA verification, independent closure and PDF download after the concurrency fix (docs/browser-vercel-capa-results.json). Cloud MFA/accessibility and mobile navigation passed separately. The initial full browser run is retained as failed diagnostic evidence; it is not falsely reported as a clean full-suite pass. Actual cloud HTTP assessment/review/all-report-format workflow and two-turn evidence chat passed. Backend-pending issue is resolved. Screenshot: docs/vercel-connected.png.

## 10 November 2026: stopped cloud worker

The frontend and API were reachable, but actual upload processing stalled because Vercel stopped all team daemons after the shared Hobby provisioned-memory quota reached 420 GB-hours. Re-requesting the configured instance confirmed the quota error. The cloud package now defaults to JOB_MODE=inline and omits the daemon, uses a 300-second function limit, and resumes existing tenant-owned queued/retry/expired work during source/assessment status polling. Dedicated worker mode remains an explicit packaging/configuration option. All 53 backend tests passed, including recovery without a worker and tenant isolation. No paid plan upgrade or local data migration was performed. Live deployment acceptance passed in request-driven mode: registration, upload/indexing, assessment/review and PDF/DOCX/CSV downloads. The cloud browser sign-up/MFA/accessibility check also passed. Evidence: docs/REQUEST_DRIVEN_DEPLOYMENT_RESULTS.json. Production deployment dpl_8bzx8EAnd1fGxNQPoq1eai3YVbFs.
