ARCHIVED: replaced by docs/VERIFYING.md, docs/ARCHITECTURE.md, docs/SECURITY.md

# Security Core Port Report

**Datum:** 2026-01-01  
**Syfte:** Portera Security Core-komponenter från copy-pastev2 till Arbetsytan som isolerad, dormant modul utan runtime-ändringar.

## Vad som portats

### Filer skapade

**Modulstruktur:**
```
apps/api/security_core/
  ├── __init__.py
  ├── config.py
  ├── privacy_gate.py
  ├── privacy_guard.py
  └── privacy_shield/
      ├── __init__.py
      ├── models.py
      ├── regex_mask.py
      ├── leak_check.py
      └── service.py
```

**Dokumentation:**
- `docs/SECURITY_CORE.md` – Dokumentation av Security Core
- `docs/SECURITY_CORE_PORT_REPORT.md` – Denna rapport

**Verifiering:**
- `apps/api/_verify/verify_security_core_import.py` – Import- och funktionstest

### Komponenter

#### 1. Privacy Shield (`privacy_shield/`)
- **models.py** – Pydantic models (PrivacyMaskRequest, PrivacyMaskResponse, MaskedPayload, PrivacyLeakError, etc.)
- **regex_mask.py** – Baseline regex masking (e-post, telefonnummer, personnummer, ID-mönster, adresser/postnummer)
- **leak_check.py** – Fail-closed leak detection
- **service.py** – Defense-in-depth pipeline (multi-pass masking → leak check → control check [inaktiv])

#### 2. Privacy Gate (`privacy_gate.py`)
- `ensure_masked_or_raise()` – Hard enforcement för extern LLM-egress
- Returnerar `MaskedPayload` (type-safe garanti)

#### 3. Privacy Guard (`privacy_guard.py`)
- `sanitize_for_logging()` – Rensar data från content och source identifiers
- `assert_no_content()` – Strikt kontroll för förbjudna nycklar
- `compute_integrity_hash()` / `verify_integrity()` – Content integrity verification

#### 4. Config (`config.py`)
- Feature flags (dormant):
  - `SECURITY_CORE_ENABLED = False`
  - `CONTROL_MODEL_ENABLED = False`
  - `privacy_max_chars = 50000`
  - `source_safety_mode = True`
  - `debug = False`

### Anpassningar vid port

1. **Imports:**
   - Relativa imports inom security_core (`from .privacy_shield.service import ...`)
   - Uppdaterade från `app.modules.privacy_shield.*` till `security_core.privacy_shield.*`

2. **Config:**
   - Ersatt `from app.core.config import settings` med `from ..config import ...`
   - Config flyttad till `security_core/config.py` (inte i main.py)

3. **Logging:**
   - Ersatt `from app.core.logging import logger` med `import logging; logger = logging.getLogger(__name__)`

4. **Control check:**
   - Behålls i `service.py` men inaktiv via `CONTROL_MODEL_ENABLED = False` (early return)
   - Minimal diff mot original för spårbarhet

## Vad som INTE aktiverats

### Runtime-integration
- ❌ **Ingen endpoint-användning** – Inga endpoints importerar eller använder Security Core
- ❌ **Ingen ersättning av befintlig masking** – `text_processing.py` förblir aktiv och oberoende
- ❌ **Ingen extern AI-integration** – Ingen kod anropar externa LLM-tjänster
- ❌ **Feature flags ej använda** – Flags är definierade men inga kod läser dem

### Verifierat
- ✅ Inga imports av `security_core` i `main.py`
- ✅ Inga imports av `security_core` i `text_processing.py`
- ✅ Befintlig masking (`text_processing.mask_text()`, `pii_gate_check()`) förblir aktiv

## Var framtida integration sker (exakta hooks)

### Hooks i `apps/api/main.py`

**Eventuella endpoints som skulle anropa extern AI måste:**
1. Använda `privacy_gate.ensure_masked_or_raise()` **innan** API-anrop
2. Acceptera endast `MaskedPayload` som input till externa API:er

**Exempel (endast illustration, inte implementerat):**
```python
from security_core.privacy_gate import ensure_masked_or_raise

@app.post("/api/projects/{project_id}/ai-summary")
async def generate_ai_summary(project_id: int, ...):
    # Hämta document.masked_text (redan maskerad av nuvarande pipeline)
    raw_text = document.masked_text
    
    # Ytterligare säkerhet via Privacy Gate (för extern AI)
    masked_payload = await ensure_masked_or_raise(raw_text, mode="strict")
    
    # Skicka till extern LLM
    response = await openai_client.chat.completions.create(
        messages=[{"role": "user", "content": masked_payload.text}]
    )
    ...
```

### Befintlig masking

**`apps/api/text_processing.py`:**
- Befintlig masking (`mask_text()`, `pii_gate_check()`) förblir aktiv
- Security Core är **alternativ** för extern AI-path, ersätter inte befintlig masking
- Nuvarande pipeline: `normalize_text()` → `mask_text()` → `pii_gate_check()`

## Verifiering

### Testresultat: ✅ PASS

**Test:** `apps/api/_verify/verify_security_core_import.py`

**Output:**
```
[1] Testing imports...
   ✓ All imports successful

[2] Testing Privacy Shield masking...
   ✓ Masking works correctly
   ✓ Masked text: Kontakta mig på [EMAIL] eller ring [PHONE]. Personnummer: [PNR]....

[3] Testing Privacy Gate...
   ✓ Privacy Gate works correctly
   ✓ MaskedPayload created: 64 chars

[4] Testing Privacy Guard...
   ✓ sanitize_for_logging works correctly
   ✓ assert_no_content correctly raises AssertionError
   ✓ assert_no_content correctly passes for safe data

[5] Verifying no endpoints import Security Core...
   ✓ No Security Core imports in endpoints (correct)

============================================================
✅ ALL TESTS PASSED
============================================================
```

### Bekräftat

- ✅ Modulen kan importeras utan fel
- ✅ Masking fungerar korrekt (e-post, telefonnummer, personnummer maskeras)
- ✅ Privacy Gate fungerar korrekt (returnerar MaskedPayload)
- ✅ Privacy Guard fungerar korrekt (sanitize_for_logging, assert_no_content)
- ✅ Inga endpoints använder Security Core (förväntat)

### Inga runtime-ändringar

- ✅ Inga endpoints ändrade
- ✅ Inga imports av Security Core i endpoints
- ✅ Befintlig masking förblir aktiv
- ✅ Feature flags definierade men olästa

## Sammanfattning

Security Core har portats från copy-pastev2 till Arbetsytan som isolerad, dormant modul. Alla komponenter (Privacy Shield, Privacy Gate, Privacy Guard) är på plats och fungerar korrekt, men modulen är **inaktiv** och används inte av några endpoints.

Modulen är förberedd för framtida extern AI-integration och kan aktiveras via feature flags när integration behövs.

