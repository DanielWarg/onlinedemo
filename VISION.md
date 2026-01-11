# VISION.md

## Vad är Arbetsytan?

Arbetsytan är en säker arbetsmiljö för journalister som hanterar känsliga tips och källor genom en strukturerad process från mottagning till läsning.

## För vem?

Reporter och redaktörer som arbetar med känsliga tips, källor och material som kräver extra säkerhet och struktur.

## Arbetsflöde

1. **Projekt** – Ett projekt skapas för att organisera material med klassificering (Offentlig, Känslig, Källkänslig)
   - Skapa manuellt eller importera från RSS/Atom feed via Scout
2. **Ingest** – Material importeras (PDF, textfiler) eller spelas in direkt (röstmemo via webbläsare)
   - Eller importera feed-items automatiskt som dokument, anteckningar och källor
3. **Automatisk sanering** – Allt material går genom deterministisk progressive sanitization pipeline (Normal → Strikt → Paranoid)
4. **Maskad vy** – Standardarbetsmiljö där all känslig information är maskerad; originalmaterial exponeras aldrig
5. **Redaktionell förädling** – Röstmemo-transkript förädlas deterministiskt till redaktionellt arbetsbart första utkast
6. **Redigering** – Dokument, anteckningar och källor kan redigeras efter import (går genom samma sanitization-pipeline)

## Vad gör Arbetsytan INTE?

- Genererar inte artiklar eller text för publicering
- Publicerar inte innehåll
- Ersätter inte journalistens bedömning eller arbete
- Är inte en redaktionssystem eller CMS
- Använder inte extern AI för transkription eller bearbetning (endast lokal STT)

## Varför spelar det roll?

- **Minska risk** – Säker hantering av känsligt material från start; allt maskeras automatiskt
- **Öka effektivitet** – Strukturerad hantering av material i projekt
- **Skydda källor** – Originalmaterial exponeras aldrig; endast maskad vy arbetas med
- **Hjälpa journalistiken** – Verktyg som stödjer journalistiskt arbete, inte ersätter det

## Teknisk approach

- **Lokal STT** – Tal-till-text via openai-whisper (ingen extern tjänst, ingen data lämnar systemet)
- **Deterministisk pipeline** – Alla transformationer är deterministiska; samma input ger samma output
- **Fail-closed** – Vid osäkerhet stängs systemet ner; inget material exponeras

## Showreel intent

Detta är ett live demo-verktyg byggt som om det vore för intern nyhetsredaktionsanvändning. Fokus ligger på att visa hur säker, strukturerad hantering av känsligt material kan fungera i praktiken.

