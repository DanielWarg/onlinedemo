# Plan: Senior showreel‑polish (Stampen Media)

## Syfte
Göra Arbetsytan **externt demobar** och tekniskt “senior‑känslig” utan att sabba nuvarande flöden.

**Primär körning**: Tailscale Funnel demo (`deploy/tailscale/`) på en domän via Caddy.

## Målbild (för annonsen)
- **Verksamhetsnära**: Scout → Projekt → Fort Knox → Spara rapport som dokument.
- **AI/dataflöden**: insamling + bearbetning + generering med tydliga gates.
- **Säkerhet & integritet**: fail‑closed, local‑first, inga secrets i git, inga råtexter i loggar.
- **Produktionsdisciplin light**: CI, migrationsdisciplin, observability‑grund, tydlig “väg till AWS”.

## Senior‑principer (hur vi jobbar, så det ser “rätt” ut)
- **Små, säkra steg**: varje ändring ska vara lätt att reviewa och enkel att rulla tillbaka.
- **Feature flags / env defaults**: allt som kan bryta demo ligger bakom flagga och är AV som default.
- **Idempotens & determinism**: rapporter och pipelines ska vara reproducerbara.
- **Error-budget UX**: inga stacktraces i UI; konsekvent svenska; tydliga tomlägen/loading/error.
- **Ingen raw content i logs**: logga endast metadata + feltyp, aldrig text/PII.
- **Migrationsdisciplin**: versionerade migrationer, inte “handskrivna ad‑hoc” ändringar.
- **Commit hygiene**: tydliga commits, inga blandade förändringar, konsekventa meddelanden.

## Scope: “Solid demo” (3–5 dagar, utan att bryta)

### 1) CI (hög signal)
- GitHub Actions som kör:
  - Backend: `pytest` (minst verifieringstester + snabb smoke på endpoints).
  - Frontend: `npm ci` + `npm run build`.
  - (Valfritt) Docker smoke: `GET /api/health`.

### 2) Docs som en senior alltid har
- `docs/DEMO_SCRIPT.md`: 5–10 steg “happy path” för intervju/demo.
- `docs/RISKS.md`: ärlig lista på vad som INTE är produktion än (auth, async jobs, observability, etc).

### 3) Auth‑struktur (utan att byta allt direkt)
- Behåll demo‑basic som default, men bygg en **abstraktion** så OIDC/SSO kan kopplas in.
- Inför enkla roller (`editor`, `admin`) och policy-check i backend.

### 4) Async jobs för STT/LLM (stabilitet)
- Problem: STT/LLM i request-loop → timeouts/frys.
- Lösning: job-tabell + endpoints:
  - start job → poll status → fetch result.
- UI: status + progress + copy (“lokal AI arbetar…”) – redan delvis infört i Fort Knox.
- Flagga: `ASYNC_JOBS=0` default så demo inte riskerar regress.

### 5) Alembic (migrations)
- Inför Alembic i `apps/api/`.
- Börja flytta schemaändringar till versionerade migrationer.
- Behåll bootstrap som “first-run” men gör uppgraderingar via migrations.

### 6) Observability light
- Standardiserade loggar med request_id (utan content).
- Hälsokoll: `/health` + `/api/health`.
- Latency-mätning för Fort Knox och STT (metadata only).

## Koppling till `projektplan.md`
Vi fortsätter bocka av:
- **Spacing/typografi**
- **Copy-pass**
utan att lägga nya features som inte behövs för showreel.

## Leverans/checkpoints
- Efter varje del: snabb Funnel-check (öppna `https://{tailnet}/` och kör DEMO_SCRIPT).
- Om något känns riskigt: flagga av, demo ska alltid fungera.

