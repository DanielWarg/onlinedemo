# Arbetsytan – Roadmap (Showreel)

Denna roadmap beskriver **hur Arbetsytan byggs steg för steg**, med tydliga stop/go-punkter.  
Fokus är **demo-first, security by default och newsroom-nära produktutveckling**.

Projektet är en **fungerande showreel**, inte en full produkt.

---

## 🎯 Övergripande mål

Bygga ett internt arbetsverktyg för journalister som:

- samlar källmaterial i projekt
- sanerar allt automatiskt
- visar endast maskad read-only-vy
- möjliggör AI-stöd **utan risk för PII-läckage**
- upplevs tryggt, lugnt och professionellt

---

## FAS 0 – Styrning & disciplin ✅

**Mål:** gemensam arbetsmodell och tydliga gränser.

Levererat:
- `agent.md` – operativt kontrakt (Plan Mode, demo-first)
- `VISION.md` – vad produkten är / inte är
- `PRINCIPLES.md` – non-negotiables
- `SECURITY_MODEL.md` – säkerhetsmodell begriplig för tech & ledning

Status: **Klar – fryst**

---

## FAS 1 – Core Platform & UI-system ✅

**Mål:** stabil grund som känns "riktig".

Levererat:
- FastAPI + Postgres
- React + Vite
- Projekt + events
- Globalt UI-system (Copy/Paste-inspirerat)
- Dashboard, projektlista, projektvy
- Modal "Skapa projekt"
- Enhetlig typografi, färger och komponenter

Status: **Klar – fryst**

---

## FAS 2 – Material ingest & läsning ✅

**Mål:** journalistens kärnarbete fungerar.

Levererat:
- Upload PDF/TXT
- Text extraction
- Read-only dokumentvy
- Inga rådata exponeras
- Materiallista per projekt

Status: **Klar – fryst**

---

## FAS 3 – Progressive Sanitization 🔒 (KRITISK)

**Mål:** bevisa att ingest är bulletproof.

Arkitektur:
- Normal → Strict → Paranoid
- Ingest fastnar aldrig
- Paranoid garanterar gate-pass
- AI/export styrs av sanitize_level

Status:
- Paranoid-path verifierad ✅
- Normal/Strict-path verifiering ✅

**STOP/GO:**
- ✅ Deterministic "safe document" passerar normal/strict → arkitekturen är fryst.

---

## FAS 4 – Narrativ låsning ✅

**Mål:** korrekt och trygg kommunikation i demo.

Levererat:
- `DEMO_NARRATIVE.md` – låsta formuleringar för demo och UI
- Alla formuleringar implementerade verbatim i UI
- Tooltips och hjälptexter matchar DEMO_NARRATIVE.md exakt
- DocumentView: "Originalmaterial bevaras i säkert lager..."
- ProjectDetail: Saneringsnivå-förklaringar + AI avstängt-förklaring
- CreateProject: Klassificering-förklaring

Status: **Klar – fryst**

---

## FAS 5 – Showreel-moduler ✅

**Mål:** maximalt signalvärde, minimal komplexitet.

Levererat:
- **Röstmemo → transcript → ingest** – Browser-inspelning, lokal STT (Whisper), deterministisk transcript-normalisering, redaktionell förädling
- Deterministisk pipeline för transkript: transcribe → normalize → process → refine → sanitize
- **STT-motor:** Whisper (konfigurerbart via `WHISPER_MODEL` env var)
  - **Default:** `medium` (~3-5GB RAM, bra balans kvalitet/hastighet)
  - **Alternativ:** `large-v3` (~6-10GB RAM, bäst kvalitet, långsammare)
  - **Dev:** `base` eller `small` för snabbare utveckling
- **Modell-caching:** Persistent cache via Docker volume (`whisper_cache`) för snabbare efterföljande transkriberingar
- **Prestanda:** Large-v3 tar ~15-20 min för första transkribering (modellladdning + CPU-inferens), medium tar ~3-5 min
- **Alternativ STT (framtida):** Arkitekturen är förberedd för motorbyte (t.ex. Silero ASR) utan endpoint-ändringar
- **Scout feed-import** – RSS/Atom feed-import med automatisk projekt-skapande
  - Preview feed innan import
  - Fulltext-extraktion från artikel-länkar (trafilatura)
  - Automatisk skapande av dokument, anteckningar (ProjectNote) och källor (ProjectSource)
  - Deduplikation baserat på feed item GUID/länk
  - SSRF-skydd (endast http/https, blockar privata IPs)
  - Redigering av dokument, anteckningar och källor efter import
  - Filnamn genereras från feed-rubrik

Status: **Klar – fryst**

---

## FAS 6 – Demo polish & live-presentation

**Mål:** arbetsgivaren ska kunna klicka själv.

- Körs på egen domän
- Stabil start/stop
- Förberedd demo-data
- Ingen "dev-känsla"

---

## FAS 7 – Freeze & intervjubruk

**Mål:** visa mognad och omdöme.

- Inga nya features
- Endast bugfix vid behov
- Fokus på resonemang, prioritering och ansvar

---

## Sammanfattning

> Vi bygger inte mycket.  
> Vi bygger rätt.  
> Och vi bevisar det steg för steg.

Nästa steg styrs alltid av aktuell **STOP/GO-punkt**, aldrig av tempo eller idéflöde.

