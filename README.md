# PharmaReg-XAI workspace

Application source, setup, test commands, and deployment instructions are in [pharmareg-xai/README.md](pharmareg-xai/README.md).

Progress, real-model verification and remaining deployment/domain validation: [DEVELOPMENT_STATUS.md](pharmareg-xai/DEVELOPMENT_STATUS.md). The application includes durable processing, reviewed source/version workflows, grounded assessments, human review, CAPA evidence, reporting and research evaluation.

Real local-AI application: http://127.0.0.1:8027 — API docs: http://127.0.0.1:8027/docs.

Existing extractive workspace: http://127.0.0.1:8010. The profiles use separate storage.

Completed controls now include MFA/SSO, signed review attestations, notifications, encrypted file storage, HTTPS, scope exclusions, and paginated risk/grouping workflows. Local verification: 51 backend tests, 6 frontend tests, and 3 browser tests; the 3 browser tests also passed on the real local-AI profile. See the status file for evidence and deployment acceptance requirements.

Cloud application: https://pharmareg-xai.vercel.app — real API, isolated PostgreSQL, private encrypted file storage and request-driven durable jobs are connected. Create a new cloud workspace; local accounts remain local. The cloud currently uses explicit extractive evidence mode, with a 4 MiB upload cap. See the Vercel deployment documentation for configuration and capacity limits.
