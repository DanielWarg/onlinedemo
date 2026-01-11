## agent.md

Operativt kontrakt för AI-assistenter (intern utvecklingsprocess). Detta dokument är inte en del av produkten – det beskriver hur repo:t hålls stabilt och showreel-säkert under utveckling.

## Roll

AI-assistenten är en operativ utförare som implementerar enligt godkända planer. Vision och produktbeslut ligger utanför assistentens ansvar.

## Plan Mode (obligatoriskt)

1. Förstå uppgiften
2. Skapa plan med tydliga steg
3. Vänta på godkännande
4. Implementera endast efter godkännande

## Hårda gränser

- Ingen implementation utan godkänd plan (gäller ALLA ändringar)
- Inga nya dokumentationsfiler (utom explicit begärt)
- Inga genererade artefakter i git
- Inga nya top-level mappar
- Inga stora refaktoreringar (endast demo-kritiska, måste ändå gå via Plan Mode)

## Progress och feedback

Långvariga operationer (>5 sekunder) måste visa progress. Användare ska alltid se att processen pågår.

## Processhantering och städning

**Processer:** Stäng alla efter användning (verifiera med `ps aux`).

**Städning (VERIFIERAD - 5 steg):**
1. Lista vad som finns
2. Verifiera vad som är aktivt/standard (kolla config)
3. Identifiera vad som INTE används
4. Ta bort endast det som verifierat inte används
5. Verifiera efter borttagning att allt viktigt finns kvar

**ALDRIG** ta bort filer/modeller utan att först VERIFIERA vad som används.

## Verifieringschecklista

- [x] Plan Mode används och plan är godkänd
- [ ] Inga nya dokumentationsfiler
- [ ] Inga genererade artefakter committas
- [x] Progress visas för långvariga operationer
- [ ] Processer stängs efter användning
- [ ] Städning är verifierad (5-stegsprocess)
- [ ] Inga aktiva modeller/filer tas bort
## Phase Overrides — Security by Design (Phase 1)

Följande undantag gäller endast för Phase 1: Security by Design enligt
docs/PHASE_1_SECURITY_BY_DESIGN_PLAN.md

- Nya dokumentationsfiler är tillåtna om de uttryckligen ingår i Phase 1-planen.
- Verifieringsscripts (`apps/api/_verify/*`) räknas inte som genererade artefakter,
  utan som obligatoriska säkerhetsbevis och får committas.
- Implementation får ske utan ny plan endast om steget redan är godkänt i Phase 1-checklistan.
- Inga andra undantag är tillåtna.
Fort Knox v1 anses klar och godkänd när samtliga punkter nedan är uppfyllda:

Deterministisk export

Samma projekt + policy + template ger samma input_fingerprint.

KnoxInputPack innehåller endast sanitiserad text (Documents + ProjectNotes), sorterat deterministiskt.

input_manifest innehåller inga textfält, endast metadata + hash.

Fail-closed i alla steg

Input gate stoppar vid sanitize-nivå, PII-gate eller size-limit.

Om FORTKNOX_REMOTE_URL saknas → FORTKNOX_OFFLINE (metadata-only), ingen rapport skapas.

Remote timeout eller schema-fel → ingen rapport sparas.

Output gate + re-ID guard stoppar deterministiskt.

Idempotens

En rapport per (project_id, policy_id, template_id, input_fingerprint).

Finns rapport redan → returneras direkt, ingen remote-call sker (även om Fort Knox är offline).

Strikt LLM-kontrakt

Fort Knox Local returnerar endast JSON enligt schema (additionalProperties:false).

All rendering till Markdown sker deterministiskt i backend-kod.

Template påverkar instruktioner/ton, inte JSON-strukturen i v1.

Audit utan innehåll

Loggar innehåller aldrig text (varken input eller output).

Sparat: policy/version/hash, engine_id, fingerprint, gate_results, timestamps.

Verifiering passerar

make verify-fortknox-v1 kör grönt:

Internal policy → PASS

External policy (provocerad) → FAIL

Re-run → idempotens bevisad

Offline-läge → korrekt error

När alla punkter ovan är uppfyllda är Fort Knox v1 design-frozen och redo att kopplas till UI.

## Manuell testchecklista – Fort Knox External Station

- [x] Snapshot: Öppna ett projekt → Fort Knox 🔒 → External → snapshot laddas (items listas med checkboxar, badges)
- [x] Compile: Kör “Kompilera Extern” → rapport eller BLOCKED visas (metadata-only fel)
- [x] Gate: Vid BLOCKED med `*_sanitize_level_too_low` → items highlightas och kan autofixas
- [x] Autofix: “Autofixa alla” → bump endpoints kallas → snapshot uppdateras → auto re-compile → PASS
- [ ] Exkludera: Avmarkera blockerande item(s) → compile igen → PASS (reducerat underlag)
- [x] Redigera: “Redigera” öppnar modal (maskad text + nivå) → spara → re-compile → PASS
- [ ] EMPTY_INPUT_SET: Avmarkera alla items → compile → tydligt felkort med UX-text
- [ ] Intern: Intern-tabben kompilerar och renderar rapport som innan
- [ ] Idempotens: Kör compile igen med samma selection → samma report_id (cache-hit i UI)
- [ ] ORIGINAL_MISSING: Autofixa dokument med saknad originalfil → får `ORIGINAL_MISSING` inline på raden → välj “Exkludera” → compile → PASS