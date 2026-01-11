## Arbetsytan – One‑pager 

Arbetsytan är en showreel som demonstrerar **hur jag bygger AI‑stöd där data är känslig**: ingest‑pipelines, sanering/normalisering, lokal STT, isolerad LLM‑användning och tydliga policy‑gates. Fokus är **security by default**, **fail‑closed** och **verifierbarhet**.

### 1) Arkitektur i en bild

```
[Web (React/Vite)]  ──HTTPS──>  [Caddy]  ──/api──>  [API (FastAPI)]
      |                                  |              |
      |                                  |              +--> [Postgres]
      |                                  |              +--> [uploads/ (original + sanerat)]
      |                                  |
      +<────────────── static dist ──────+

Fort Knox (LLM):
[API] ──HTTP──> [fortknox-local (FastAPI)] ──HTTP──> [llama.cpp server] ──GGUF model (lokalt)

STT:
[API] ──local──> faster-whisper (modell-cache lokalt/volym)
```

### 2) Dataflöde (det som är viktigt)

- **Ingest** (dokument, anteckningar, Scout‑items, röstmemo)
  - Text extraheras/normaliseras.
  - **Sanitize‑pipeline** maskar deterministiskt (PII + datum/tid i strict/paranoid).
  - UI jobbar alltid på **maskad vy** (inte råtext).
- **Fort Knox** (rapport)
  - Bygger ett deterministiskt `KnoxInputPack` (manifest + fingerprint).
  - **Input gate**: kräver rätt sanitize‑nivå + PII‑gate + size‑gränser.
  - **LLM‑körning** sker lokalt (via `fortknox-local/` + `llama.cpp`).
  - **Output gate**: PII‑gate + re‑ID guard (skydd mot citat/återidentifiering).
  - Rapport kan sparas som dokument (men exkluderas från framtida Fort Knox‑underlag).

### 3) Hotbild (kort, realistiskt)

- **Oavsiktlig exponering** (UI/loggar): råtext i UI, råtext i loggar, felaktig export.
  - Mitigation: maskad vy som standard, metadata‑only logging, fail‑closed gates.
- **SSRF / otrygga källor** (Scout/import): attacker via URL‑fetching.
  - Mitigation: SSRF‑skydd och strikt hantering av externa resurser (se `docs/SECURITY.md`).
- **Prompt injection / data exfiltration**: LLM kan “läcka” input i output.
  - Mitigation: input är redan sanerat; output gate + re‑ID guard stoppar citat/identifierare.
- **Felkonfiguration i demo** (t.ex. att man råkar aktivera osäkert läge).
  - Mitigation: demo‑safe defaults (features av som standard), tydliga env‑flaggor.

### 4) Varför fail‑closed (och hur det märks)

Arbetsytan tar hellre ett “nej” än en osäker leverans:
- Om sanering inte räcker → input gate stoppar.
- Om output innehåller PII eller rå frasering → output gate stoppar.
- Samma underlag → samma fingerprint/idempotens (enklare att revidera och debugga).

### 5) Produktion vs demo (ärlig uppdelning)

**Demo (detta repo)**
- Kör lokalt + kan exponeras via Tailscale Funnel för visning.
- Basic auth räcker för demo.
- `ASYNC_JOBS` kan slås på för att visa job‑flow (202 + polling).
- Observability är “light” (request‑id + metadata‑logg).

**Produktion (vad som saknas för att vara “klart”)**
- **Auth/SSO** (OIDC), roll‑/behörighetsmodell, audit‑krav per kund.
- **Nyckelhantering/secrets** (Vault/KMS), rotationsrutiner, policy‑as‑code.
- **Kö/backpressure** (riktig jobbkörning: Redis/Celery/Arq), timeouts och retries.
- **Övervakning** (metrics/tracing), larm, dashboards, SLO:er.
- **Data governance** (retention, exportkontroller, DLP‑policy), klassificeringsflöden.
- **Hardening** (rate limits, WAF‑regler, dependency scanning, signed images).

### 6) “LangChain‑flöde” (skiss)

Arbetsytan använder idag ett eget, deterministiskt Fort Knox‑flöde. Om man vill visa **LangChain** utan att ändra säkerhetsprinciperna kan flödet se ut så här:

1. **Loader (RunnableLambda)**: hämta `KnoxInputPack` från DB (endast sanerad text + manifest).
2. **PromptTemplate**: policy‑styrd prompt med tydliga constraints (ingen råtext, korta citat, schema).
3. **LLM**: lokal modell via OpenAI‑kompatibel endpoint (llama.cpp) eller via `fortknox-local/`.
4. **Structured output**: `PydanticOutputParser`/`JsonOutputParser` + strikt validering/retries.
5. **Guards** (efter LLM): samma `pii_gate_check` + `re_id_guard` som idag.
6. **Persist**: spara `KnoxReport` + idempotens på fingerprint + engine_id.

Nyckeln: LangChain får vara “orkestrering”, men **gates + determinism + fail‑closed** förblir ägda av Arbetsytan.

**Opt‑in i denna repo:** Vi har en separat endpoint som inte påverkar standardflödet: `POST /api/fortknox/compile/langchain`.
Aktiveras med `FORTKNOX_PIPELINE=langchain` samt antingen:
- **OpenAI (demo)**: `FORTKNOX_LC_PROVIDER=openai`, `OPENAI_API_KEY`, (valfritt `FORTKNOX_LC_MODEL`)
- **Lokal endpoint**: `FORTKNOX_LC_PROVIDER=local`, `FORTKNOX_LC_BASE_URL`, (valfritt `FORTKNOX_LC_API_KEY`, `FORTKNOX_LC_MODEL`)
Rapporter sparas med `engine_id=langchain` för separat idempotens/cache.

### 7) Vidare läsning

- Arkitektur: `docs/ARCHITECTURE.md`
- Flöden: `docs/FLOWS.md`
- Säkerhet: `SECURITY_MODEL.md`, `docs/SECURITY.md`
- Deploy/runbook: `deploy/tailscale/README.md`

