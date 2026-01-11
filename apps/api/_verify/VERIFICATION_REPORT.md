# Verifieringsrapport: Recording Transcript Sanitization

**Datum:** 2026-01-01  
**Syfte:** Säkerställa att röstmemo-transkript behandlas exakt som övriga dokument: normalize → mask → progressive sanitization, och att UI default alltid är maskad vy.

## Pipeline-analys

### POST /api/projects/{project_id}/recordings

**Var kommer raw transcript ut från transcribe_audio()?**
- **Fil:** `apps/api/main.py`
- **Rad:** 554
- **Funktion:** `transcribe_audio(str(audio_path))`
- **Returnerar:** `raw_transcript` (str)

**Vilken funktion kör normalize/mask/sanitize?**
- **Normalisering 1 (transcript-specifik):** `normalize_transcript_text(raw_transcript)` (rad 568)
- **Processering:** `process_transcript(...)` (rad 581) - strukturerar till markdown + pre-scan PII masking
- **Förädling:** `refine_editorial_text(...)` (rad 584) - redaktionell förädling
- **Normalisering 2 (text):** `normalize_text(processed_text)` (rad 600)
- **Progressive sanitization:** Rad 609-641 - exakt samma pipeline som TXT upload:
  - `mask_text(normalized_text, level="normal")`
  - `pii_gate_check(masked_text)`
  - Om fail → `mask_text(..., level="strict")`
  - Om fail → `mask_text(..., level="paranoid")`

**Verifierat:**
- ✅ Recordings går via **exakt samma ingest-pipeline** som TXT upload
- ✅ Document.masked_text sparas korrekt (rad 657)
- ✅ Progressive sanitization pipeline används identiskt

## Testresultat

**Test:** `verify_recording_sanitization.py`

**Input (test transcript med PII):**
```
mail test@example.com
telefon 070-123 45 67
personnummer 19900101-1234
```

**Resultat:**
- ✅ **PII maskering:** Alla originalsträngar borttagna
  - `test@example.com` → `[EMAIL]`
  - `070-123 45 67` → `[PHONE]`
  - `19900101-1234` → `[PERSONNUMMER]`

- ✅ **Mask tokens:** Alla tokens finns i output
  - `[EMAIL]`, `[PHONE]`, `[PERSONNUMMER]`

- ✅ **PII gate:** PASSED (normal masking)
  - `sanitize_level: normal`
  - `pii_gate_reasons: None`
  - `usage_restrictions: {"ai_allowed": true, "export_allowed": true}`

**Test:** Event metadata verifiering
- ✅ **Event `recording_transcribed`:** Endast metadata (size, mime, duration_seconds, recording_file_id)
- ✅ **Ingen transcript:** Inget transcript-innehåll i event_metadata

## Loggning

**Kontrollerat:**
- ✅ Alla loggar är metadata-only:
  - `[AUDIO] Audio file received: filename=X, size=Y bytes, mime=Z`
  - `[AUDIO] Transcription finished: transcript_length=X chars`
  - `[AUDIO] Transcript normalized: length=X chars (was Y)`
- ✅ Ingen raw transcript loggas
- ✅ Ingen `print()` av transcript-innehåll

**Filer kontrollerade:**
- `apps/api/main.py` - endast metadata i loggar (rad 531, 552, 556, 570, 687, 690)
- Verifieringsskript loggar endast för test (tillåtet)

## UI verifiering

**DocumentView.jsx:**
- ✅ Visar `document.masked_text` (rad 92)
- ✅ Inget alternativ för "raw view" eller "unmasked view"
- ✅ UI visar alltid maskad vy som default (endast maskad vy finns)

**API schemas:**
- ✅ `DocumentResponse` innehåller `masked_text` (schemas.py rad 62)
- ✅ `DocumentListResponse` innehåller **INTE** `masked_text` (endast metadata)

## Exakt var saneringen sker

### Fil: `apps/api/main.py`

**Funktion:** `upload_recording()` (rad 506-718)

**Saneringssteg:**
1. **Rad 554:** `raw_transcript = transcribe_audio(...)` - STT
2. **Rad 568:** `normalized_transcript = normalize_transcript_text(raw_transcript)` - transcript-normalisering
3. **Rad 581:** `processed_text = process_transcript(...)` - strukturering + pre-scan PII masking
4. **Rad 584:** `processed_text = refine_editorial_text(processed_text)` - redaktionell förädling
5. **Rad 600:** `normalized_text = normalize_text(processed_text)` - text-normalisering
6. **Rad 609-641:** Progressive sanitization pipeline:
   - Normal masking → PII gate check
   - Om fail: Strict masking → PII gate check
   - Om fail: Paranoid masking → PII gate check (måste passera)
7. **Rad 657:** `masked_text=masked_text` - sparar maskerad version i DB

### Fil: `apps/api/text_processing.py`

**Funktioner:**
- `normalize_transcript_text()` - transcript-specifik normalisering
- `process_transcript()` - strukturering + pre-scan PII masking (säkerhetsåtgärd)
- `refine_editorial_text()` - redaktionell förädling
- `normalize_text()` - text-normalisering
- `mask_text()` - progressive masking (normal/strict/paranoid)
- `pii_gate_check()` - PII gate verification

## Sammanfattning

**Status:** ✅ **PASS**

**Konklusion:**
- Recordings går via **exakt samma pipeline** som TXT upload
- All PII maskeras korrekt enligt progressive sanitization
- UI visar alltid maskad vy (endast maskad vy finns)
- Event metadata innehåller endast metadata (ingen transcript)
- Loggning är metadata-only (ingen raw transcript)

**Inga ändringar behövs** - implementationen är korrekt.

## Verifieringsfiler

- `apps/api/_verify/verify_recording_sanitization.py` - automatiserat test
- `apps/api/_verify/VERIFICATION_REPORT.md` - denna rapport

