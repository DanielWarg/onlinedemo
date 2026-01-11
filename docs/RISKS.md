# Risker och vad som återstår innan “riktig produktion”

Det här repo:t är en **showreel/MVP**. Nedan är en ärlig lista över vad en senior team‑setup normalt gör innan produktion.

## 1) Auth/SSO och behörigheter
- Nu: demo‑auth (Basic) är ok för lokal demo.
- Prod: OIDC/SSO (t.ex. Cognito/Entra) + RBAC/ABAC, audit‑logg, sessioner.

## 2) Bakgrundsjobb (STT/LLM)
- Nu: delar av STT/LLM körs i request‑cykeln och kan vara långsamma.
- Prod: job queue/worker (t.ex. Celery/RQ), status‑API, retries, backpressure.

## 3) Migrationsdisciplin
- Nu: bootstrap + idempotenta SQL‑ändringar finns.
- Prod: versionerade migrationer (Alembic), reproducibla deploys, rollback‑plan.

## 4) Observability
- Nu: hälsokoll och metadata‑loggar finns, men begränsat.
- Prod: structured logs + correlation ids, metrics/tracing, dashboards/alerts.

## 5) Testning/CI
- Nu: verifieringstester finns.
- Prod: CI som kör tester/build på varje PR + åtminstone en smoke/e2e.

## 6) Data governance
- Nu: “maskad vy” + fail‑closed gates minskar risk för läckage.
- Prod: retention policies, backup/restore, incident‑runbooks, DPIA.

## 7) Driftmiljö (AWS)
- Demo: Tailscale Funnel är perfekt för showreel.
- Prod: container‑drift (ECS/EKS), secrets management, VPC, IAM, kostnadskontroll.

