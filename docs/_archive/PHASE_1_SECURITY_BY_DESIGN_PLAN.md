ARCHIVED: replaced by docs/VERIFYING.md, docs/ARCHITECTURE.md, docs/SECURITY.md

# Phase 1: Security by Design - Implementation Plan

## 🧠 Working Principles — Phase 1: Security by Design

Detta dokument styr hur arbetet ska utföras, inte bara vad som ska göras.

### Grundprincip

**Vi bygger inte nya produktfeatures. Vi bygger enforcement + verifiering.**

Vi aktiverar och bevisar säkerhetsbeteenden som redan finns eller som är direkt portabla från copy-pastev2.

### Säkerhetsfilosofi

- **Säkerhet ska vara automatisk** – användaren ska inte behöva tänka, välja eller konfigurera.
- **Systemet ska alltid vara fail-closed:**
  - Vid osäkerhet ska systemet blockera, inte fortsätta tyst.
- **Alla säkerhetspåståenden ska vara verifierbara i Docker med körbara scripts.**
  - Ingen verifiering = inget klart.

### Arbetsmetod (obligatorisk)

Varje steg ska:
- peka på exakta filer och rader som ändras
- ha tydliga acceptance criteria
- avslutas med PASS/FAIL-verifiering

**Inga antaganden. Inga gissningar. Inga "bör fungera".**

- UI-ändringar måste verifieras i browser mode.
- Backend-ändringar måste verifieras via `_verify`-scripts.

### Arkitektoniska regler

- **Inget innehåll (text, filer, identifiers) får nå:**
  - events
  - logs
  - audit trails
- **Delete betyder riktig delete:**
  - DB + filstore
  - inga orphans
  - verifierat efteråt
- **Metadata får loggas – aldrig content.**

### Definition of Done

En punkt i denna plan är inte klar förrän:
- verifieringsscript körs i Docker
- resultatet är PASS
- beviset kan visas utan förklaring

**Målet med Phase 1 är att vi utan tvekan ska kunna säga:**  
*"I detta verktyg kan du arbeta säkert utan att röja källor, utan att bryta mot GDPR av misstag, och när du raderar data är den verkligen borta."*

## ✅ PHASE 1 — Security by Design (Checklist för Cursor)

### 0) Setup & Guardrails

- [x] Skapa dokument: `docs/PHASE_1_SECURITY_BY_DESIGN_PLAN.md` och lägg in checklistan (denna) så den lever i repot
- [x] Bekräfta körmiljö: `docker compose ps` visar api + postgres healthy
- [x] Bekräfta hur verifieringsscripts körs i Arbetsytan: `docker compose exec api python _verify/<script>.py` (working dir `/app`)

### Milestone 1 — Event "No Content" Enforcement (Max effekt / Min risk)

#### 1.1 Inventory: var ska enforcement in?

- [x] Lista alla ställen i `apps/api/main.py` där `ProjectEvent` skapas (rad-länkar)
- [x] Bekräfta att `apps/api/security_core/privacy_guard.py` innehåller:
  - `sanitize_for_logging()`
  - `assert_no_content()`
- [x] Definiera "förbjudna fält" (en lista i docs + i verify-script): se "Definitions & Guardrails" ovan för komplett lista

#### 1.2 Implementera enforcement i alla events

- [x] Importera Privacy Guard i `apps/api/main.py`
- [x] Skapa en liten helper (t.ex. `_safe_event_metadata(meta: dict, context: str) -> dict`) som:
  - kör `sanitize_for_logging(meta, context=...)`
  - kör `assert_no_content(sanitized, context=...)`
  - returnerar `sanitized`
- [x] Byt ut samtliga `ProjectEvent(... metadata=...)` så att metadata alltid passerar helpern
- [x] Säkerställ fail-closed:
  - DEV (`DEBUG=true`): raise AssertionError (så vi ser fel direkt)
  - PROD (`DEBUG=false`): droppa fält och fortsätt (enligt policy)
- [x] Dokumentera vilken env-flagga som styr "DEV vs PROD": `DEBUG` (default: `false`)

#### 1.3 Verifieringsscript: event policy

- [x] Skapa: `apps/api/_verify/verify_event_no_content_policy.py`
- [x] Testfall 1: försök skapa event med förbjuden nyckel (t.ex. `{"text": "content"}`) → AssertionError i DEV
- [x] Testfall 2: försök skapa event med source identifier (t.ex. `{"filename": "secret.pdf"}`) → AssertionError i DEV
- [x] Testfall 3: skapa event med harmlös metadata (t.ex. `{"project_id": 123}`) → PASS
- [x] Scriptet ska köras i **DEV mode** (`DEBUG=true`) för att bevisa fail-closed hårt
- [x] Optional: testfall som visar PROD "drops" utan crash (för demo-trovärdighet)
- [x] Scriptet ska vara körbart i Docker och skriva tydligt PASS/FAIL

#### 1.4 Acceptance / Bevis

- [x] Kör i Docker: `docker compose exec api python _verify/verify_event_no_content_policy.py`
- [x] Verifiera i browser mode att UI fortfarande fungerar och events laddar

### Milestone 2 — Secure Delete (Project + Allt innehåll) med Verifiering

#### 2.1 Inventory: vad ingår i "Project delete"?

- [x] Lista alla data som måste bort när projekt raderas:
  - documents + deras filer
  - recordings + audio + transcript-filer
  - notes (inkl ev. attachments/bilder om ni har)
  - events
- [x] Identifiera var filerna ligger (upload dir / filstore paths)
- [x] Bekräfta befintlig `delete_project()` i `apps/api/main.py` (rad ~219) och vad den gör idag

#### 2.2 Implementera "wipe + orphan detection + idempotency"

- [x] Före delete: räkna antal filer som tillhör projektet (utan att logga filnamn)
- [x] Radera DB-rader i rätt ordning / via cascade så att allt kopplat försvinner
- [x] Wipe filstore:
  - ta bort filer kopplade till projektet (documents/recordings/notes)
  - verifiera att filerna faktiskt är borta
- [x] Orphan detection:
  - hitta filer i projektets filområde som inte längre har DB-referens
  - efter wipe: ska det vara 0
- [x] Fail-closed:
  - om wipe/verifiering misslyckas → returnera error och blockera delete (ingen "silent success")
- [x] Loggpolicy:
  - logga bara antal (counts), inga paths eller filenames
- [x] Idempotent:
  - kör delete igen på samma projekt → ska inte krascha / ska ge kontrollerat svar

#### 2.3 Verifieringsscript: secure delete

- [x] Skapa: `apps/api/_verify/verify_secure_delete.py`
- [x] Scriptet ska:
  - skapa projekt
  - ladda upp minst 1 document
  - skapa 1 recording (eller ladda upp) så det blir filer på disk
  - skapa 1 note
  - verifiera att filer finns på disk innan delete
  - kalla delete endpoint
  - verifiera:
    - DB: inga rader kvar kopplade till projektet
    - filsystem: inga filer kvar kopplade till projektet
    - orphan count = 0
- [x] Scriptet ska vara körbart i Docker och skriva PASS/FAIL

#### 2.4 Delete-confirmation UX (minimal, för demo-trovärdighet)

- [x] UI: Delete kräver bekräftelse (skriv projektnamn / "RADERA" eller liknande)
- [x] UI visar efter delete en "Deleted project" bekräftelse (utan att återge namn/filer)
- [x] Detta är inte "ny funktionalitet" – det är ett UX-skal för att visa att deletion är seriöst

#### 2.5 Acceptance / Bevis

- [x] Kör i Docker: `docker compose exec api python _verify/verify_secure_delete.py`
- [x] Verifiera i UI: skapa projekt + fyll med material + delete → projektet försvinner och går inte att nå via URL efteråt
- [x] Verifiera delete-confirmation flow i browser mode

### Milestone 3 — "Verify Suite" + Make target

#### 3.1 Samla Phase 1 verifieringar

- [x] Säkerställ att följande scripts finns och kör:
  - `verify_event_no_content_policy.py`
  - `verify_secure_delete.py`
  - (befintliga) `verify_recording_sanitization.py`
  - (befintliga) `verify_transcript_normalization.py`
  - (befintliga) `verify_enhanced_transcript_pipeline.py`

#### 3.2 Lägg till "one command"

- [x] Lägg till `make verify-security-phase1` (eller motsvarande) som kör samtliga scripts i rätt ordning i Docker
- [x] Output ska tydligt visa PASS/FAIL per script

#### 3.3 Acceptance / Bevis

- [x] Kör: `make verify-security-phase1` → allt PASS i Docker

### Definition of Done (Phase 1)

- [x] Events kan inte råka innehålla content eller source identifiers (bevisat via verify-script)
- [x] Secure delete tar bort DB + filstore och lämnar 0 orphans (bevisat via verify-script)
- [x] Allt går att verifiera med ett kommando i Docker
- [x] Browser-mode smoke test: skapa → arbeta → delete → inte nåbart efteråt

### "No guessing" regler (som Cursor måste följa)

- Alla förändringar ska peka på exakt fil + rad där det ändrades
- Inga "jag tror" – varje claim måste ha ett verifieringssteg
- Inga UI-ändringar utan browser-verifiering

## Scope

**Vad som ingår:**

- Event "no content" enforcement (Privacy Guard integration)

- Secure Delete med filstore wipe och verifiering

- Verifieringsscript för alla security-invariants

- Fail-closed policy vid osäkerhet

- Delete-confirmation UX (minimal, för demo-trovärdighet)

**Vad som INTE ingår:**

- Extern AI-integration (Security Core förblir dormant)

- Ersättning av befintlig masking (text_processing.py förblir aktiv)

- Ny datamodell eller migrationer

## Definitions & Guardrails

### Förbjudna fält i Events/Logs/Audit

**Content-nycklar (aldrig tillåtna):**
- `body`, `text`, `content`, `transcript`, `note_body`, `file_content`, `payload`, `query_params`, `query`, `segment_text`, `transcript_text`, `file_data`, `raw_content`, `original_text`, `headers`, `authorization`, `cookie`

**Source identifier-nycklar (aldrig tillåtna när `SOURCE_SAFETY_MODE=true`):**
- `ip`, `ip_address`, `client_ip`, `remote_addr`, `x-forwarded-for`, `x-real-ip`, `user_agent`, `user-agent`, `referer`, `referrer`, `origin`, `url`, `uri`, `filename`, `filepath`, `file_path`, `original_filename`, `querystring`, `query_string`, `cookies`, `cookie`, `headers`, `host`, `hostname`

**Tillåtna metadata (exempel):**
- `project_id`, `document_id`, `note_id`, `event_type`, `actor`, `count`, `size`, `mime`, `duration_seconds`, `sanitize_level`, `classification`

**Källa:** `apps/api/security_core/privacy_guard.py` (`_FORBIDDEN_CONTENT_KEYS`, `_FORBIDDEN_SOURCE_KEYS`)

### DEV vs PROD Mode

**Env-flagga:** `DEBUG` (default: `false`)

**Beteende:**
- **DEV mode** (`DEBUG=true`): `assert_no_content()` raises `AssertionError` vid förbjudna nycklar (fail-closed, hårdt stopp)
- **PROD mode** (`DEBUG=false`): `sanitize_for_logging()` droppar förbjudna fält tyst, fortsätter (fail-closed, mjukt stopp)

**Verifiering:**
- Verify-scripts körs i **DEV mode** för att bevisa fail-closed hårt
- Optional: testfall som visar PROD "drops" utan crash

**Källa:** `apps/api/security_core/config.py` (`debug = os.getenv("DEBUG", "false").lower() == "true"`)

## Inventory: copy-pastev2 Security Modules

### 1. Privacy Guard (Event Policy)

**Filer:**
- `copy-pastev2/backend/app/core/privacy_guard.py`
- `copy-pastev2/backend/app/modules/transcripts/service.py` (användning)
- `copy-pastev2/backend/app/modules/record/service.py` (användning)
- `copy-pastev2/backend/app/modules/projects/router.py` (användning)

**Vad gör den:**
- `sanitize_for_logging()` - Rensar content och source identifiers från metadata
- `assert_no_content()` - Strikt kontroll att data inte innehåller förbjudna nycklar
- Fail-closed: DEV mode raises AssertionError, PROD mode drops fields

**Hur används den:**
- ALLA event-metadata går via `sanitize_for_logging()` + `assert_no_content()`
- Exempel: `audit_metadata = sanitize_for_logging({"title": title}, context="audit")` → `assert_no_content(audit_metadata, context="audit")`

**Status i Arbetsytan:**
- ✅ Porterad till `apps/api/security_core/privacy_guard.py` (identisk implementation)
- ❌ Används INTE i events (ingen enforcement)

### 2. Secure Delete (Purge + File Wipe)

**Filer:**
- `copy-pastev2/backend/app/modules/record/purge.py` (purge_expired_records)
- `copy-pastev2/backend/app/modules/transcripts/service.py` (delete_transcript)
- `copy-pastev2/backend/app/modules/projects/file_storage.py` (delete_file)

**Vad gör den:**
- Hard delete med CASCADE i DB
- Filstore wipe (tar bort alla filer från disk)
- Verifiering att inga orphans finns kvar
- Idempotent (kan köras flera gånger säkert)

**Hur används den:**
- `purge_expired_records()` - GDPR retention purge
- `delete_transcript()` - Hard delete med filstore wipe
- Verifiering: räknar filer före/efter, kontrollerar att alla är borta

**Status i Arbetsytan:**
- ✅ `delete_project()` finns i `apps/api/main.py:219`
- ❌ Saknar filstore wipe verifiering
- ❌ Saknar orphan detection
- ❌ Använder `os.remove()` utan verifiering

### 3. Verification Scripts

**Filer:**
- `copy-pastev2/scripts/test_purge.py`
- `copy-pastev2/scripts/comprehensive_security_test.py`
- `copy-pastev2/scripts/check_security_invariants.py`

**Vad gör de:**
- Testar event "no content" policy
- Testar secure delete med verifiering
- Testar filstore wipe
- Körs i Docker för reproducerbarhet

**Status i Arbetsytan:**
- ✅ Verifieringsscript finns i `apps/api/_verify/`
- ❌ Saknar script för event policy enforcement
- ❌ Saknar script för secure delete verifiering

## Gap Analysis: Arbetsytan

### Gap 1: Event "No Content" Enforcement

**Nuvarande:**
- Events skapas med `event_metadata` direkt (t.ex. `{"name": project.name}`)
- Ingen `assert_no_content()` kontroll
- Risk: content kan läcka i events

**Behöver:**
- Integrera `privacy_guard.assert_no_content()` i alla event-skapande
- Använda `sanitize_for_logging()` för metadata
- Fail-closed: raise AssertionError i DEV, drop fields i PROD

**Filer att ändra:**
- `apps/api/main.py` - alla `ProjectEvent` skapande (rad 135, 207, 294, 428, 694, 812, 1079)

### Gap 2: Secure Delete Verifiering

**Nuvarande:**
- `delete_project()` tar bort filer med `os.remove()` men verifierar inte
- Ingen orphan detection
- Ingen verifiering att alla filer är borta

**Behöver:**
- Verifiera filstore wipe (räkna filer före/efter)
- Detektera orphans (filer utan DB-referens)
- Fail-closed: om verifiering misslyckas, logga fel och blockera delete

**Filer att ändra:**
- `apps/api/main.py:219` - `delete_project()` funktion

### Gap 3: Verification Scripts

**Nuvarande:**
- Verifieringsscript finns men saknar event policy och secure delete tests

**Behöver:**
- `verify_event_no_content_policy.py` - testar att events aldrig innehåller content
- `verify_secure_delete.py` - testar secure delete med filstore wipe

**Filer att skapa:**
- `apps/api/_verify/verify_event_no_content_policy.py`
- `apps/api/_verify/verify_secure_delete.py`

## Milestones

### Milestone 1: Event "No Content" Enforcement ✅ COMPLETED

**Mål:** Alla events ska gå via Privacy Guard med fail-closed policy.

**Filer att ändra:**
- ✅ `apps/api/main.py` - lägg till imports och enforcement i alla event-skapande

**Acceptance criteria:**
- ✅ Alla `ProjectEvent` skapande använder `sanitize_for_logging()` + `assert_no_content()` (via `_safe_event_metadata()`)
- ✅ Test: försök skapa event med `{"text": "content"}` → AssertionError i DEV
- ✅ Test: försök skapa event med `{"filename": "secret.pdf"}` → AssertionError i DEV (source identifier)
- ✅ Verifieringsscript: `verify_event_no_content_policy.py` passerar

**Verifiering:**
```bash
docker compose exec -e DEBUG=true api python _verify/verify_event_no_content_policy.py
# Expected: ✅ ALL TESTS PASSED
# Result: ✅ PASSED (4/4 tests passed, 2025-01-02)
```

**Implementation notes:**
- Created helper function `_safe_event_metadata()` in `main.py` (line 18-34)
- Updated all 11 `ProjectEvent` creations to use `_safe_event_metadata()`
- Removed forbidden keys: `filename` from `document_uploaded` and `note_image_added` events
- Created verification script: `apps/api/_verify/verify_event_no_content_policy.py`

### Milestone 2: Secure Delete med Verifiering ✅ COMPLETED

**Mål:** `delete_project()` ska verifiera filstore wipe och detektera orphans.

**Filer att ändra:**
- ✅ `apps/api/main.py:240` - `delete_project()` funktion

**Acceptance criteria:**
- ✅ Räknar filer före delete (documents, recordings, journalist note images)
- ✅ Tar bort alla filer från disk
- ✅ Verifierar att alla filer är borta (ingen orphan)
- ✅ Loggar endast metadata (antal filer, inga filnamn/paths)
- ✅ Fail-closed: om verifiering misslyckas, logga fel och blockera delete

**Verifiering:**
```bash
docker compose exec api python _verify/verify_secure_delete.py
# Expected: ✅ ALL TESTS PASSED
# Result: ✅ PASSED (3/3 tests passed, 2025-01-02)
```

**Implementation notes:**
- Implemented 5-phase secure delete:
  1. Count all files (documents, recordings, journalist note images)
  2. Delete files from disk
  3. Verify no orphans remain (fail-closed if orphans detected)
  4. Delete DB records (CASCADE)
  5. Log only metadata (privacy-safe)
- HTTPException(500) raised if orphans detected
- Created verification script: `apps/api/_verify/verify_secure_delete.py`

### Milestone 3: Verification Scripts ✅ COMPLETED

**Mål:** Komplett verifieringssuite för alla security-invariants.

**Filer att skapa:**
- ✅ `apps/api/_verify/verify_event_no_content_policy.py`
- ✅ `apps/api/_verify/verify_secure_delete.py`
- ✅ `Makefile` - `verify-security-phase1` target

**Acceptance criteria:**
- ✅ Script kan köras i Docker
- ✅ Script testar fail-closed behavior
- ✅ Script verifierar att inga content/source identifiers läcker
- ✅ Script verifierar filstore wipe

**Verifiering:**
```bash
make verify-security-phase1
# Expected: Alla verifieringsscript passerar
# Result: ✅ PASSED (7/7 tests passed, 2025-01-02)
```

**Implementation notes:**
- Created `verify_event_no_content_policy.py` (4 tests)
- Created `verify_secure_delete.py` (3 tests)
- Added `make verify-security-phase1` target to Makefile
- All tests run in Docker with DEBUG=true for fail-closed proof

## Implementation Order

1. **Milestone 1** (Event enforcement) - Maximal effekt, minimal risk
2. **Milestone 2** (Secure delete) - Kräver Milestone 1 för logging
3. **Milestone 3** (Verification scripts) - Verifierar Milestone 1+2

## Risker och Mitigering

**Risk 1: Breaking changes i events**
- Mitigering: Testa i Docker först, behåll backward compatibility i metadata-struktur

**Risk 2: Filstore paths olika mellan copy-pastev2 och Arbetsytan**
- Mitigering: Använd `UPLOAD_DIR` från Arbetsytan, adaptera path-logik

**Risk 3: Olika datamodell (Project vs Record)**
- Mitigering: Adaptera delete-logik för Project-struktur (documents, recordings, notes, images)

## "No Guessing" Policy

Alla claims har referens:
- Event enforcement: `copy-pastev2/backend/app/modules/transcripts/service.py:674` (assert_no_content usage)
- Secure delete: `copy-pastev2/backend/app/modules/record/purge.py:25` (purge_expired_records)
- Privacy Guard: `copy-pastev2/backend/app/core/privacy_guard.py:140` (assert_no_content implementation)

## "Fail-Closed" Policy

- Event enforcement: DEV mode raises AssertionError, PROD mode drops fields
- Secure delete: Om verifiering misslyckas, blockera delete och logga fel
- Verification scripts: Alla tester måste passa, annars fail

---

## RUNBOOK — E2E Verification (Arbetsytan)

**Datum:** 2026-01-02  
**Mål:** Bevisa att verktyget fungerar som journalistisk arbetsyta och att "Security by Design" håller i praktiken.  
**Resultatformat:** PASS/FAIL per steg + länkar till bevis (screenshots/loggar) + verifieringsscripts.

### 0) Förutsättningar (måste vara sant innan start)

- [ ] Docker Desktop igång
- [ ] Repo: Arbetsytan
- [ ] Du kör från repo-root
- [ ] Inga gamla volymer som stör (om ni vill ha ren test)

#### 0.1 Starta miljön (ren och reproducerbar)

```bash
docker compose down -v
docker compose up -d --build
docker compose ps
```
**Expected:** api healthy, postgres healthy, web up

#### 0.2 Sanity-check API

```bash
docker compose logs api --tail 50
```
**Expected:** Inga tracebacks, inga "crash loop"

### 1) Backend-verifiering (måste PASS innan UI)

Kör alla verifieringsscripts som redan finns.

```bash
docker compose exec api python _verify/verify_recording_sanitization.py
```
**Expected:** ✅ PASS

```bash
docker compose exec api python _verify/verify_transcript_normalization.py
```
**Expected:** ✅ PASS

```bash
docker compose exec api python _verify/verify_enhanced_transcript_pipeline.py
```
**Expected:** ✅ PASS

**Om något failar här: STOP. Fix först.**

### 2) Browser E2E — "Journalist Workflow" (huvudtest)

**Mål:** Skapa projekt → lägg in källmaterial → transkribera → skapa dokument → anteckningar → export (om finns) → event trail.

#### 2.1 Skapa projekt

- [ ] Öppna webben (din lokala url)
- [ ] Klicka "Create project"
- [ ] Sätt namn: `E2E - Källskyddstest 2026-01-02`
- [ ] Skapa

**Expected:** Projektet syns i listan och öppnas utan fel

**Bevis:** Screenshot på projektlistan + projektvyn.

#### 2.2 Ladda upp dokument (källmaterial)

- [ ] I projektet: "Documents" → Upload
- [ ] Ladda upp en PDF eller textfil (testmaterial)
- [ ] Öppna dokumentvyn

**Expected:** Dokument finns listat och går att öppna

**Bevis:** Screenshot dokumentlistan + öppnat dokument.

#### 2.3 Röstmemo → transkribering

- [ ] Gå till "Röstmemo/Transcription"
- [ ] Ladda upp audio (eller record om den finns)
- [ ] Vänta tills transkribering klar (status ska visas)
- [ ] Kontrollera att output är strukturerad:
  - Sammanfattning
  - Nyckelpunkter
  - Tidslinje
  - Fullständigt transkript

**Expected:** Inget crash, text visas, och enhanced förbättringar syns (t.ex. "i form av", "sådan")

**Bevis:** Screenshot av transcript-view.

#### 2.4 Skapa anteckning (journalist notes)

**Mål:** Notes ska kännas logiskt och proffsigt (inte 3 knappar på olika ställen).

- [ ] Skapa ny anteckning från ett ställe (primär CTA)
- [ ] Titel: `Vinklar / Hypoteser`
- [ ] Klistra in en text (copy/paste) med känsliga bitar (fake email/telefon)

**Expected:**
- Anteckningen sparas
- UI blir inte rörigt
- Inga PII-läckor i events/loggar (se steg 3)

**Bevis:** Screenshot notes-lista + öppnad anteckning.

#### 2.5 Skapa "Document draft" från transcript (om flödet finns)

- [ ] Skapa ett dokument/draft av transcriptet (om ni har knapp)
- [ ] Kontrollera att dokumentet är normaliserat (stycken, rubriker)

**Expected:** Skapas utan fel, och går att öppna som dokument.

**Bevis:** Screenshot där draft skapats och syns i documents.

#### 2.6 Event trail (audit)

- [ ] Öppna "Events"/"Timeline"
- [ ] Kontrollera att events finns för:
  - `project_created`
  - `document_uploaded`
  - `recording_uploaded` / `transcribed`
  - `note_created` / `updated`
  - etc

**Expected:** Inga event innehåller innehåll (bara metadata)

**Bevis:** Screenshot på event trail.

### 3) Security E2E — Bevis i praktiken

Detta är "sexigheten": ni bevisar att systemet skyddar användaren även om användaren inte tänker på det.

#### 3.1 "No content in events" — praktiskt bevis

- [ ] I UI: öppna event trail och bekräfta visuellt: inga transkript/texter finns där
- [ ] Backend: `docker compose exec api python -c "<script som dumpa senaste events>"` (om ni har ett verify-script för detta ännu, använd det)

**Expected:**
- Events innehåller inga fält som `text`/`body`/`content`/`transcript`/`filename`/`path`
- När Milestone 1 är implementerad ska detta styrkas med: `verify_event_no_content_policy.py`

#### 3.2 Logs-check (anti-leak)

```bash
docker compose logs api --tail 200
```

**Expected:** Inga transkript-texter, inga filpaths, inga filenames med känslig info.

#### 3.3 Secure Delete — "riktig delete"

**Mål:** Radera projekt och bevisa att det är borta på riktigt.

- [ ] I UI: Delete project (med bekräftelse)
- [ ] Försök öppna samma URL igen

**Expected:** 404 / "Not found"

- [ ] Kontrollera att projektet inte syns i listan
- [ ] Efter Milestone 2: kör `verify_secure_delete.py` för bevis

**Bevis:**
- Screenshot: "Project deleted" + 404 vid direktlänk
- Script-PASS i Docker

### 4) Post-run: Evidence pack (för showreel)

Skapa en mapp (lokalt) och samla bevis:

- [ ] Screenshots: projektlista, dokument, transcript, note, events, delete
- [ ] Output från verifieringsscripts (copy/paste från terminal)
- [ ] "Docker ps" output

**Resultat:** En liten "evidence bundle" som kan visas för chef/tech lead.

### 5) Pass/Fail kriterier (hårda)

**FAIL direkt om:**
- [ ] Transkribering kraschar eller blir tom
- [ ] Event trail innehåller innehåll (transkript, notes, doc-text)
- [ ] Logs innehåller innehåll eller filpaths som identifierar källa
- [ ] Delete tar bort projekt i UI men det går att nå via URL
- [ ] Något verify-script failar

**PASS om:**
- [ ] Journalisten kan skapa projekt, hantera material, skapa transcript, skriva notes
- [ ] Event trail visar aktivitet utan innehåll
- [ ] Delete är verklig och verifierad

### Nästa steg (så vi får detta "på räls")

När Phase 1-milestones är implementerade:

- [ ] Lägg till `make verify-e2e` som kör:
  - `verify_*` scripts
  - plus en liten "smoke" som skapar projekt + raderar

