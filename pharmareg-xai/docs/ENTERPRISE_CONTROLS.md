# Identity, records and deployment controls

## MFA and SSO

System configuration includes authenticator enrollment, confirmation, one-use recovery codes and disabling after reauthentication. Enabling/disabling MFA revokes old sessions and rotates the current tokens. TOTP accepts the adjacent 30-second clock windows and rejects replay. Preserve SECRET_KEY: it protects encrypted MFA secrets and OIDC PKCE verifiers.

Set OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_REDIRECT_URI and, for a confidential client, OIDC_CLIENT_SECRET. Register the exact frontend callback URL with the provider. HTTPS is required outside loopback development. An administrator links each existing member to the provider's exact subject identifier in settings. Email matching never provisions or links an identity. Authorization-code exchange validates PKCE, one-use browser-bound state, issuer, audience, authorized party, expiration, signature and nonce. Enabled application MFA still applies after SSO. Signed fixture tests verify these controls; live identity-provider acceptance requires the deployment's provider configuration.

## Review attestations

Findings, CAPAs and generated reports support explicit meaning, consent and password/MFA reauthentication. The HMAC seal binds signer identity, time, statement and record fingerprint. Verification reports both seal validity and whether the record subsequently changed. Preserve SIGNATURE_HMAC_KEY (or SECRET_KEY fallback). These are application review attestations; formal electronic-record validation and legal acceptability are organizational decisions, not a software-generated certification.

## Notifications and scope

The inbox contains private pending-review, failed-job and due/overdue CAPA reminders. Embedded and standalone workers synchronize every minute; the inbox also refreshes reminders on access. Unique per-user event keys prevent repeated daily reminders. Preferences control reminder categories and the due-date window. These are in-app notifications; SMTP is used for explicitly requested password recovery, not unsolicited reminder email.

Assessment drafts retain per-requirement exclusion rationales, reviewer identity, review time and frozen approved requirement snapshots. Exclusions produce source-linked NOT_APPLICABLE findings pending final human review, without invoking a model to infer compliance.

Documents, assessments, findings/risk, CAPA, reports, team, audit and evaluation history use server pagination. Risk counts cover the full filtered result; displayed rows cover the current page. Department/document membership can overlap, so membership totals may exceed unique finding totals.

## Encryption and HTTPS

Set ENCRYPT_STORAGE=true and a separately protected 64-hex-character STORAGE_ENCRYPTION_KEY before uploading sensitive files. AES-256-GCM protects newly uploaded source originals, CAPA attachments and generated report files. Downloads authenticate and decrypt; processing uses temporary decrypted files removed on completion. Database text, extracted passages and JSON require database/volume encryption configured by the operator. Previously stored plaintext files are not automatically converted. Keep encryption keys separately backed up; losing them prevents decryption. Test restoration with the correct keys.

For loopback HTTPS, run `./scripts/start.ps1 -TLS -Port 8043`. It generates a short-lived localhost certificate without installing trust roots. Trust `storage/tls/localhost.crt` explicitly in test clients. Production requires externally supplied TLS_CERT_FILE/TLS_KEY_FILE or the Caddy overlay and a real domain; see deploy/compose.tls.yml. HTTPS_ENCRYPTED_RESULTS.json records an executed certificate-verified local HTTPS assessment/report workflow with file encryption enabled.

`python scripts/configure_deployment.py` generates a separate ignored deployment environment file and refuses overwrite. Preserve its secrets. Use `docker compose --env-file deploy/.env.deployment up --build -d --wait` on a Docker-capable host. Inspect `/api/system/readiness` as administrator for actual database/Redis/Chroma checks and configured controls. This endpoint sends no test mail and never declares production certification.

## Deployment acceptance

Run `python scripts/verify_deployment.py --url http://127.0.0.1:8080 --require-services`. It requires actual PostgreSQL, Redis and HTTP Chroma, processes sources through the worker, executes assessment/review and downloads all report formats. `.github/workflows/deployment.yml` builds those services, executes acceptance, restarts API/worker and repeats. CI intentionally uses deterministic embeddings/extractive mode to test service integration without downloading neural weights; the separate real local-AI browser and REAL_STACK_RESULTS evidence cover actual models. Docker is unavailable on the current Windows host, so this CI deployment gate has not been executed here.

## Release validation

The release validation page records evidence references, reviewer qualifications, statements and status. It does not invent qualifications or approve itself. Independent expert datasets, live SMTP/antivirus/SSO acceptance, public TLS, infrastructure encryption and applicable formal regulatory/security/accessibility validation remain operator acceptance requirements. Automated axe checks cover configured WCAG rules on tested pages; they are not a complete accessibility audit.
