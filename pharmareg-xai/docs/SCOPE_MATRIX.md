# Scope coverage — current continuation

This replaces the initial baseline scope matrix. The complete original request is preserved in MASTER_REQUIREMENTS.txt. DEVELOPMENT_STATUS.md is authoritative for executed verification and remaining deployment/domain work.

| Area | Implemented software | Verification/boundary |
|---|---|---|
| Authentication and organizations | Argon2/JWT, TOTP/recovery, OIDC code/PKCE/subject links, rotation/revocation, recovery/outbox/SMTP, profiles, roles, member management, organization isolation, browser renewal | Unit/integration/browser tests; real SMTP credentials unavailable |
| Documents and sources | Five formats, bulk uploads, checksums, original storage, version lineage/dates/department, archive/search, controlled official import, malware integration | Authentic FDA PDF and pinned fetch verified; live antivirus unavailable |
| Extraction/OCR | Physical PDF pages, Office tables/sheets, OCR fallback, heading/sentence chunks and source excerpts | Real image-only OCR verified; Office rendered pagination intentionally unavailable |
| Requirement review | Candidate extraction, original wording, reviewed statements/designation/applicability/material elements and immutable review versions | Expert approval workflow; legal interpretation is not automated certification |
| Embedding/retrieval | Hash baseline or real Sentence Transformers, batches, provenance checks/reindex, BM25/RRF, tenant/model Chroma, actual cross-encoder | Actual semantic/Chroma/reranker execution; remote container deployment pending |
| Assessment | Saved/editable wizard drafts, reasoned per-requirement exclusions, frozen config/review versions, durable execution, structured five-status findings, material elements, guarded citations/quotes, gaps and original proposals | Real-model attempts and errors preserved; semantic/legal sufficiency needs expert review |
| Explainability | Split evidence, exact excerpts, authenticated highlighted page images/deep links, original downloads, element coverage/limitations/corrections | Browser and backend source checks; highlighting limited by source text layer |
| Risk/CAPA | Internal configurable matrix, persisted factors, owner/plan/due dates, state history, files/checksums, independent evidenced closure | Backend and expanded browser tests |
| Chat | Persistent user-private multi-turn sessions, configured local/external grounded generation and extractive mode | Two actual local-model turns verified; no external transmission |
| Reports | Snapshot PDF/DOCX/CSV, physical page/section/chunk/hash references, human/model distinction, risk/CAPA manifest, DOCX page fields | All formats generated/downloaded in integration and real-stack verification attempts; browser PDF |
| Evaluation | Datasets/annotations/second-reviewer approval, retrieval baselines, classification/confusion/per-class metrics and labeled claim/element quality | Test fixtures are not an independent domain gold set |
| Dashboard/admin | Database-backed stats, trends/status/authority/department/overdue filters, audit review/integrity, settings/team | Browser navigation/mobile checks; some legacy lists remain capped |
| Jobs/database | Normalized version/job/session/dataset/evidence-attachment records, atomic leases/retries/uniqueness, explicit migrations, Redis coordinator and limiter | SQL concurrency/recovery/fresh and upgrade tests; real PostgreSQL/Redis deployment pending |
| Security/operations | File validation, limits, RBAC/tenant checks, CSP/escaping, source SSRF/DNS/IP pinning, scanner fail-closed, SMTP TLS, audit seals, encrypted backup/restore | Actual restore/tamper/SSRF/transport-control tests; deployment credentials and formal security validation pending |
| Packaging | Locked frontend/base dependencies, ML requirements, API/frontend/Chroma Dockerfiles, worker/Compose health checks, startup/profile/verification/runbook | Docker absent here; no claim of completed production infrastructure validation |

| Enterprise records | Reauthenticated consented review attestations, hash seals/staleness checks, release validation evidence | Controlled fixtures and browser verification; no legal certification |
| Notifications | Private inbox/preferences, due/overdue CAPA and review/job events, worker scheduling/deduplication | Backend and browser checks; no unsolicited email |
| File protection/TLS | AES-GCM source/attachment/report encryption, protected downloads/processing, HTTPS/Caddy | Certificate-verified local HTTPS full workflow; public domain and DB-volume encryption are operator controls |

Remaining externally dependent work: Docker-capable deployment verification, configured infrastructure/services, independent qualified annotations, and regulatory/security/electronic-record validation. Advanced filtering/grouping, explicit exclusion rationale, notification scheduling, MFA/SSO and review attestations are implemented. Automated accessibility checks pass tested pages; comprehensive human accessibility review remains external acceptance.
