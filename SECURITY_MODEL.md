# SECURITY_MODEL.md

## Grundprincip

**Security by default** – Säkerhet kräver inga användarval; det är standard. Systemet är säkert från start, inte efter konfiguration.

**Maskad vy som standard** – Alla arbetar i maskerad miljö som utgångspunkt. Känslig information är dold tills explicit åtkomst begärs.

**Fail-closed vid osäkerhet** – Vid osäkerhet stängs systemet ner; ingen "fail-open". Bättre att blockera än att exponera känsligt material.

## Arbetsyta

### Maskad vy (standard)

Standardarbetsmiljö där all känslig information är maskerad. Användare ser strukturerad information utan att exponera källor eller känsliga detaljer.

Originalmaterial bevaras i säkert lager och exponeras aldrig i arbetsytan. Alla dokument visas endast i maskad vy.

## Klassificering

Material klassificeras i tre nivåer:

- **Normal** – Allmänt material utan särskild känslighet
- **Känslig** – Material som kräver extra försiktighet
- **Källkänslig** – Material som direkt kan exponera källor

Klassificering påverkar:

- **Text** – Maskering av känsliga delar i normalvy
- **Metadata** – Filnamn, titlar och previews maskeras eller döljs
- **Loggning** – Känsligare material loggas mindre detaljerat
- **Åtkomst** – Strikta åtkomstregler för källkänsligt material

## Roller och åtkomst

- **Owner (reporter)** – Full åtkomst till eget material i maskad vy
- **Editor** – Kan arbeta med material i maskad vy
- **Admin (drift)** – Systemadministration, aldrig innehållsåtkomst

## Loggpolicy

**Vad som loggas:**
- Säkerhetshändelser (åtkomstförsök, autentisering)
- Incidenter (fel, avvikelser)
- Systemdrift (tillgänglighet, prestanda)

**Vad som aldrig loggas:**
- Innehåll i material
- Källinformation
- Användaraktivitet för personaluppföljning

Loggar är för säkerhet och incidenthantering, inte för övervakning av användare.

## AI och externa tjänster

**Lokal STT** – Tal-till-text hanteras lokalt via openai-whisper. Ingen data lämnar systemet vid transkription.

**Extern AI** – Ej implementerat. Om extern AI skulle användas i framtiden:

- Endast via maskad export
- Alltid opt-in
- Ingen rådata lämnar systemet – endast maskerat, strukturerat material exporteras

## Designintention

Säkerhetsmodellen är designad för att:

- **Skydda journalistiskt arbete** – Källor och material skyddas från exponering
- **Minimera risken att göra fel** – Standardinställningar är säkra; fel kräver aktiv handling
- **Göra rätt beteende till standard** – Säkerhet är default, inte valfritt

