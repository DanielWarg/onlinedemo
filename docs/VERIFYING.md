# Verifiering

## Översikt

Arbetsytan har omfattande verifieringsprocesser för att säkerställa kvalitet och säkerhet.

## Makefile Targets

### Grundläggande verifiering
```bash
make verify              # Smoke tests (health, hello, project CRUD)
make verify-fas0         # Dokumentationscheck (agent.md, VISION.md, etc.)
make verify-fas1        # Backend/frontend health checks
make verify-fas2        # Document upload och sanering
make verify-fas4-static # UI-text och narrativ låsning
```

### Specifika verifieringar
```bash
make verify-sanitization        # Saneringspipeline
make verify-projects-e2e       # Projects E2E scenarios
make verify-transcription-quality # STT kvalitet
make verify-feed-import        # Feed import funktionalitet
make verify-security-phase1    # Security policies
```

## Fort Knox Verifiering

### verify-fortknox-v1-loop

Automatisk loop som hanterar restarts och compose-uppdateringar.

**Körning:**
```bash
make verify-fortknox-v1-loop
```

**Process:**
1. Kör `verify_fortknox_v1.py`
2. Om exit code 100 (NEEDS_RESTART):
   - Läser `/tmp/fortknox_compose_update_needed`
   - Kopierar compose-fil från container
   - Restartar API
   - Väntar på `/health`
   - Fortsätter loop (max 8 attempts)
3. Om exit code 0: PASS ✅
4. Om exit code 1+: FAIL ❌

**State Machine:**
- Använder `TEST_RESULTS_DIR/fortknox_state/` för persistent state
- Flaggor: `t5_5a_done`, `t5_waiting_for_remote_restore`, `t5_remote_restored_for_5b`, `t5_report_created`, `t5_remote_restored`, `t5_done`
- Deterministisk utan loopar

### Test 5: FORTKNOX_OFFLINE

Testar att systemet fungerar även när remote offline:

1. **Sub-test 5a:** Nytt projekt, tom remote URL → FORTKNOX_OFFLINE error
2. **Sub-test 5b:** Befintlig rapport returneras även när remote offline (idempotens)

**Resultat:** JSON i `apps/api/test_results/fortknox_v1_verify.json`

## Verify Scripts

### verify_fortknox_v1.py
- Test 1: Skapa projekt med innehåll
- Test 2: Compile internal → PASS
- Test 3: Compile external → FAIL (expected)
- Test 4: Idempotency (dedupe)
- Test 5: FORTKNOX_OFFLINE (med state machine)

### verify_projects_e2e.py
E2E-scenarier för projects:
- Scenario A: Create → List → View
- Scenario B: Update → Delete
- Scenario C: Documents CRUD
- Scenario D: Notes CRUD

### verify_sanitization.py
Verifierar saneringspipeline:
- Normalisering
- Maskering (e-post, telefon, personnummer)
- PII gate check

## Exit Codes

- **0:** PASS
- **1:** FAIL
- **100:** NEEDS_RESTART (hanteras av Makefile-loop)

## Resultat

Alla verifieringar sparar resultat i:
- `apps/api/test_results/*.json`
- `apps/api/test_results/fortknox_state/` (state flags)
