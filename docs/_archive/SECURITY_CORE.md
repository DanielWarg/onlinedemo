ARCHIVED: replaced by docs/VERIFYING.md, docs/ARCHITECTURE.md, docs/SECURITY.md

# Security Core

Security Core är en isolerad, dormant modul som porterats från copy-pastev2 för framtida extern AI-integration. Modulen är **inte aktiv** i nuvarande runtime och används inte av några endpoints.

## Vad är Security Core?

Security Core består av tre huvudkomponenter:

### 1. Privacy Shield
Defense-in-depth masking pipeline för PII (Personally Identifiable Information):

- **Regex masking** – Baseline masking av e-post, telefonnummer, personnummer, ID-mönster, adresser/postnummer
- **Multi-pass masking** – Flera pass för att fånga edge cases och överlapp
- **Leak check** – Fail-closed kontroll som blockerar om PII-mönster återstår efter masking
- **MaskedPayload** – Type-safe garanti att text är maskerad (endast Privacy Shield kan skapa detta)

Pipeline:
1. Baseline regex mask (måste alltid köras)
2. Leak check (blockerande)
3. Control check (advisory, strict mode) – **INAKTIV** (CONTROL_MODEL_ENABLED=False)

### 2. Privacy Gate
Hard enforcement för extern LLM-egress:

- **ensure_masked_or_raise()** – Enda sättet att förbereda text för extern LLM
- Fail-closed: Om masking misslyckas eller leak detekteras blockeras request
- Returnerar `MaskedPayload` som kan skickas säkert till externa API:er

### 3. Privacy Guard
Paranoid content protection för loggning:

- **sanitize_for_logging()** – Rensar data från content och source identifiers innan loggning
- **assert_no_content()** – Strikt kontroll att data inte innehåller förbjudna nycklar
- Förhindrar att känslig information loggas i audit/event-loggarna

## När ska Security Core användas?

**EJ nuvarande användning** – Modulen är dormant och används inte i nuvarande runtime.

**Framtida användning:**
- För extern AI-integration (t.ex. OpenAI API, Anthropic Claude)
- Alla externa LLM-anrop måste gå via Privacy Gate innan API-anrop
- Använd `privacy_gate.ensure_masked_or_raise()` för att säkerställa att text är maskerad

## Lokal AI vs extern AI

### Lokal AI (nuvarande)
- **openai-whisper** – Tal-till-text körs lokalt, ingen data lämnar systemet
- Används för röstmemo-transkription
- Ingen masking krävs eftersom data aldrig lämnar systemet
- Implementerad i `text_processing.py`

### Extern AI (framtida)
- Externa LLM-tjänster (OpenAI, Anthropic, etc.)
- Data måste skickas utanför systemet
- **Kräver Privacy Gate** – All text måste gå via `privacy_gate.ensure_masked_or_raise()` innan API-anrop
- Security Core är förberedd för denna integration men är inaktiv

## Aktuell status

**Status:** Inaktiv, dormant, opt-in via feature flag

**Feature flags** (definierade i `security_core/config.py`, ej använda):
- `SECURITY_CORE_ENABLED = False` – Huvudflagga (dormant)
- `CONTROL_MODEL_ENABLED = False` – Control check path inaktiv

**Ingen integration:**
- Inga endpoints använder Security Core
- Befintlig masking i `text_processing.py` förblir aktiv och oberoende
- Ingen extern AI-integration

## Arkitektur

### Defense-in-depth pipeline

```
Raw Text
  ↓
[Privacy Shield: Regex Mask (multi-pass)]
  ↓
[Leak Check (fail-closed)]
  ↓
[MaskedPayload] ← Type-safe garanti
  ↓
[Privacy Gate: ensure_masked_or_raise()]
  ↓
Extern LLM API (framtida)
```

### Modulstruktur

```
apps/api/security_core/
  ├── __init__.py
  ├── config.py              # Feature flags (dormant)
  ├── privacy_gate.py        # Hard enforcement för extern LLM
  ├── privacy_guard.py       # Content protection för loggning
  └── privacy_shield/
      ├── __init__.py
      ├── models.py          # Pydantic models
      ├── regex_mask.py      # Baseline masking
      ├── leak_check.py      # Fail-closed leak detection
      └── service.py         # Defense-in-depth pipeline
```

## Framtida integration

### Var hooks ska ligga

Om extern AI-integration implementeras måste följande endpoints använda Privacy Gate:

**Hooks i `apps/api/main.py`:**
- Eventuella endpoints som anropar extern AI måste använda `privacy_gate.ensure_masked_or_raise()` **innan** API-anrop
- Exempel (endast illustration, inte implementerat):
  ```python
  from security_core.privacy_gate import ensure_masked_or_raise
  
  @app.post("/api/projects/{project_id}/ai-summary")
  async def generate_ai_summary(project_id: int, ...):
      # Hämta document.masked_text
      raw_text = document.masked_text  # Redan maskerad av nuvarande pipeline
      
      # Ytterligare säkerhet via Privacy Gate (för extern AI)
      masked_payload = await ensure_masked_or_raise(raw_text, mode="strict")
      
      # Skicka till extern LLM
      response = await openai_client.chat.completions.create(
          messages=[{"role": "user", "content": masked_payload.text}]
      )
      ...
  ```

**Befintlig masking:**
- `apps/api/text_processing.py` – Befintlig masking (`mask_text()`, `pii_gate_check()`) förblir aktiv
- Security Core är **alternativ** för extern AI-path, ersätter inte befintlig masking

## Verifiering

Kör verifieringsscript:
```bash
cd apps/api
python _verify/verify_security_core_import.py
```

Scriptet bekräftar:
- Modulen kan importeras utan fel
- Masking fungerar på testtext
- Inga endpoints använder Security Core

