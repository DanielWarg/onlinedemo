# Säkerhet

## Security-by-Default

Arbetsytan är byggd med säkerhet som standard, inte som valfritt tillägg.

## Sanering Pipeline

### Normalisering → Maskering → PII Gate

All text går genom tre steg:

1. **Normalisering** (`normalize_text`)
   - Standardiserar whitespace
   - Normaliserar teckenkodning
   - Förbereder för maskering

2. **Maskering** (`mask_text`)
   - E-post: `test@example.com` → `EMAIL`
   - Telefon: `070-123 45 67` → `PHONE`
   - Personnummer: `19900101-1234` → `PERSONNUMMER`
   - Progressiv sanering (Normal → Strikt → Paranoid)

3. **PII Gate** (`pii_gate_check`)
   - Verifierar att all PII är maskerad
   - FAIL om känslig information kvarstår
   - Används både vid input och output

## Metadata-Only Logs

**Princip:** Loggar aldrig råtext eller känslig information.

- Dokument: Endast ID, filnamn, storlek, typ
- Transkript: Aldrig råtranskript i loggar
- Events: Endast metadata, inget innehåll
- API-responses: Maskerad vy som standard

## SSRF-skydd

### Feed Import
- Endast http/https URLs
- Blockar privata IPs (10.x, 172.16-31.x, 192.168.x)
- Timeout (30s)
- Max storlek (10MB)

### Trafilatura Integration
- Säker fulltext-extraktion
- Validering av URL innan fetch

## Fort Knox Security

### Input Gate
- Sanitize level validation
- PII gate check
- Size limits

### Output Gate
- PII gate på output
- Re-ID Guard (kontrollerar identifierare)

### Idempotens
- Säkerställer att samma input ger samma output
- Fungerar även när remote offline

## Klassificering

Tre nivåer:
- **Offentlig:** Standard sanering
- **Känslig:** Strikt sanering
- **Källkänslig:** Paranoid sanering

## Fail-Closed

Vid osäkerhet:
- Systemet stänger ner
- Inget material exponeras
- Fel loggas (metadata endast)

## Originalmaterial

- Originalmaterial bevaras i säkert lager
- Exponeras aldrig i arbetsytan
- Endast maskerad vy visas
