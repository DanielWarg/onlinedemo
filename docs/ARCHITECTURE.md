# Arkitektur

## Översikt

Arbetsytan är en säker arbetsmiljö för journalister som hanterar känsligt material. Systemet är byggt med FastAPI (backend) och React (frontend), med PostgreSQL som databas.

## Core-moduler

### Project
Central enhet för att organisera material. Varje projekt har:
- Klassificering (Offentlig, Känslig, Källkänslig)
- Status (aktiv, arkiverad)
- Due date (valfritt)
- Metadata (namn, beskrivning)

### Document
Dokument som tillhör ett projekt. Hanterar:
- PDF och textfiler
- Automatisk textextraktion
- Maskerad vy som standard
- Originalmaterial bevaras säkert

### Notes
Anteckningar kopplade till projekt:
- ProjectNote (projektrelaterade anteckningar)
- JournalistNote (journalistens privata anteckningar)
- Strukturerat innehåll med kategorier

### Sources
Källor kopplade till projekt:
- URL-baserade källor
- Metadata (typ, titel, kommentar)
- SSRF-skydd vid import

### Export
Exportfunktionalitet för projektdata (metadata endast, inget känsligt innehåll).

## Scout/Feed Import

### Feed Import
- RSS/Atom feed-importering
- Automatisk skapande av projekt från feeds
- Fulltext-extraktion med trafilatura
- Deduplikation baserat på GUID/länk

### Scout Integration
- Skapa projekt direkt från Scout-items
- Integration med Scout-modal i UI

## STT/Röstmemo

### Lokal tal-till-text
- **Engine:** faster-whisper (default) eller Whisper
- **Modell:** Konfigurerbar (base, small, medium, large-v3)
- **Pipeline:**
  1. Audio upload → sparas permanent
  2. Transkribering med lokal STT
  3. Normalisering av transkript
  4. Redaktionell förädling (refine_editorial_text)
  5. Skapande av Document med maskerad vy

### Modell-caching
- Global singleton för STT-engine
- Persistent cache i Docker volume
- Preload vid startup för snabbare första användning (valfritt; styrs av `PRELOAD_STT=1`)

## Fort Knox

### Komponenter

#### KnoxInputPack
Deterministisk struktur som samlar:
- Documents (text + metadata)
- Notes (text + metadata)
- Sources (metadata endast, ingen URL i payload)
- Manifest (fingerprint för idempotens)

#### Input Gate
Validering innan remote call:
- Sanitize level check (normal/strikt/paranoid)
- PII gate check
- Size check

#### Idempotens Check
Kontrollerar om rapport redan finns baserat på input fingerprint. Returnerar befintlig rapport om matchning hittas.

#### Remote URL Check
Om FORTKNOX_REMOTE_URL saknas → FORTKNOX_OFFLINE error (men idempotens fungerar ändå).

#### Remote Call
Anropar Fort Knox Local eller remote service med KnoxInputPack. Test mode använder fixtures.

#### Output Gate + Re-ID Guard
- PII gate check på output
- Re-ID guard (kontrollerar att inga identifierare läckt ut)

#### KnoxReport
Sparas i databasen med:
- Policy ID och version
- Ruleset hash
- Input fingerprint
- Gate results
- Rendered markdown

## Teknisk stack

- **Backend:** FastAPI (Python 3.9+)
- **Frontend:** React + Vite
- **Database:** PostgreSQL
- **STT:** faster-whisper / Whisper (lokal)
- **Deployment:** Docker Compose
