ARCHIVED: replaced by docs/ARCHITECTURE.md, docs/FLOWS.md, docs/VERIFYING.md

Perfekt val 👍
Då gör vi **Phase 1 till ett låst, sparbart styrdokument** som du kan:

* spara i repo:t
* referera till i dialog med Cursor
* använda som “stoppskylt” så ni inte överbygger
* visa för rekryterare som bevis på produktmognad

Nedan är **hela Phase 1-planen i ett enda sammanhängande dokument**, färdigt att copy/paste:a rakt in i t.ex.
`docs/PHASE_1_JOURNALIST_WORKSPACE.md`

---

# Phase 1 – Journalistisk arbetsyta (låst plan)

## Syfte

Phase 1 ska resultera i en **komplett, trovärdig och användbar journalistisk arbetsyta** där en journalist kan:

* samla material
* tänka privat
* strukturera sitt arbete
* förstå var projektet befinner sig
* avsluta och ta materialet vidare

Målet är **inte maximal funktionalitet**, utan **arbetsro, kontroll och trovärdighet**.

Phase 1 ska vara:

* demo-redo
* stabil
* begriplig för både journalist och rekryterande chef

---

## Grundprinciper (låsta)

* Projektet är journalistens primära arbetsrum
* Innehåll delas upp i tydliga typer med olika semantik
* Ingen AI får påverka journalistens privata tankearbete
* All spårbarhet sker via metadata och events, aldrig via innehåll
* Minsta möjliga funktionalitet som känns “klar att jobba i”

---

## Innehållstyper i Phase 1

### 1. Dokument

Syfte: strukturerat, publicerbart material
Egenskaper:

* normaliserat
* sanerat
* kan exporteras
* kan delas vidare

Status: **KLAR**

---

### 2. Röstmemo / Transkription

Syfte: rå källa (intervju, möte, reflektion)
Egenskaper:

* lokalt STT (faster-whisper)
* enhanced normalisering
* saniterad text
* aldrig privat tankearbete

Status: **KLAR**

---

### 3. Anteckningar

Syfte: journalistens privata arbetsyta
Egenskaper:

* rå text
* smart paste (plain text)
* bilder som passiva referenser
* ingen AI
* ingen språklig normalisering
* separat modell (JournalistNote)

Status: **KLAR**

---

## Byggstenar som tillkommer i Phase 1

Phase 1 kompletteras med **tre redaktionella byggstenar** som skapar kontroll, kontext och avslut.

---

## Byggsten A — Projektstatus (redaktionellt läge)

### Syfte

Svarar på frågan:
**“Var är projektet i arbetsprocessen?”**

Detta är inte tasks eller workflow, utan ett redaktionellt läge.

### Tillåtna statusar (låsta)

* Research
* Bearbetning
* Fakta-check
* Klar
* Arkiverad

### UI

* Dropdown i projekt-header
* Alltid synlig
* Diskret färgkodning
* Ingen progress-bar
* Ingen automation

### Teknik & säkerhet

* Lagras som enum på Project
* Default: Research
* Event: `project_status_changed`
* Event innehåller endast metadata (old/new, user, timestamp)
* Påverkar inget innehåll, ingen AI, ingen sanitering

Status: **✅ KLART**

---

## Byggsten B — Källor / Referenser

### Syfte

Gör projektet journalistiskt försvarbart.

Svarar på frågan:
**“Vad bygger detta på?”**

### Funktionalitet (minimal)

* Lista med källor kopplade till projekt
* Varje källa har:

  * titel
  * typ (länk / person / dokument / annat)
  * frivillig kommentar

### Principer

* Allt manuellt
* Ingen auto-fetch
* Ingen analys
* Ingen AI
* Ingen koppling till Scout

### Säkerhet

* Källor är metadata
* Innehåller inget råmaterial
* Kan visas utan att röja innehåll

Status: **✅ KLART**

---

## Byggsten C — Export / Avslut

### Syfte

Ge känslan av att projektet kan **lämnas vidare**.

### Funktionalitet (Phase 1)

* Export av Dokument:

  * Markdown / PDF / DOCX
* Val:

  * inkludera metadata eller inte
* Anteckningar:

  * ingår aldrig som default
* Röstmemo:

  * endast om aktivt valt

### Principer

* Ingen publicering
* Ingen CMS-integration
* Ingen delning i systemet

Status: **✅ KLART**

---

## Kontrollpanelen (overview)

### Ska innehålla

* Projektöversikt
* Due dates (enkel)
* Placeholder-boxar för:

  * Scout
  * Fort Knox

### Scout (Phase 2)

* RSS-övervakning
* 24h historik
* Leads

Scout **byggs inte i Phase 1**, endast visuellt placeholder.

---

## Det som EXPLICIT INTE ingår i Phase 1

* Tasks / to-dos
* Kommentarer / samarbete
* AI-sammanfattningar
* CMS-koppling
* Taggar
* Versionshantering
* Automatiska workflows

Allt ovan är **Phase 2+**.

---

## Definition of DONE – Phase 1

Phase 1 är klar när en journalist kan:

* arbeta i projektet utan att sakna något grundläggande
* förstå projektets status direkt
* hålla isär:

  * rå källor
  * privata tankar
  * publicerbart material
* avsluta arbetet och ta med sig resultatet vidare

När Phase 1 är klar:
➡️ **Vi slutar bygga funktioner och går över till polish + showreel.**

---

## Rekommenderad byggordning

1. Projektstatus
2. Källor / Referenser
3. Export / Avslut

En byggsten i taget. Full verifiering mellan varje.

---

När detta dokument är sparat och låst kan vi:

* plocka ut **en exakt Cursor-prompt per byggsten**
* jobba metodiskt utan att tappa riktning

Säg bara **“gå vidare till Projektstatus – prompt”** så tar vi nästa steg exakt där.
