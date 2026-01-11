ARCHIVED: replaced by docs/VERIFYING.md, docs/ARCHITECTURE.md, docs/SECURITY.md

# STT Benchmark Matrix - Prestanda & Kvalitet

## Översikt

Jämförelse mellan Whisper och faster-whisper med base/small modeller.

## Resultat

| Engine | Model | Run 1 (s) | Run 2 (s) | Avg (s) | CPU Peak (%) | CPU Avg (%) | RAM Peak (GB) | Word Count | Nonsense Ratio | Swedish Chars |
|--------|-------|-----------|-----------|---------|--------------|-------------|---------------|------------|----------------|---------------|
| faster_whisper | base | 17.4 | 12.9 | 15.2 | 687.8 | 515.1 | 0.81 | 1150 | 0.174 | 0.061 |
| faster_whisper | small | 47.5 | 34.4 | 41.0 | 696.4 | 493.8 | 1.54 | 1169 | 0.166 | 0.063 |
| whisper | base | 59.1 | 58.5 | 58.8 | 973.0 | 893.8 | 0.92 | 1107 | 0.172 | 0.059 |
| whisper | small | 187.9 | 170.4 | 179.2 | 1005.2 | 888.2 | 1.81 | 1173 | 0.168 | 0.063 |

## Kvalitetsjämförelse (Snippets)

### faster_whisper base

**Början:**
- Raw: En sak, vad är en konflikt egentligen. Där finns det hur många olika definitioner som helst....
- Enhanced: En sak, vad är en konflikt egentligen. Där finns det hur många olika definitioner som helst....

**Mitten:**
- Raw: Och det är ofta det här vi gärna gärna vill prata jättemycket om om vi själva är involverade  inom form av svår situation. Vi vill genompratta om att Anders eller Malin eller Vemner nu kan vara  har a...
- Enhanced: Och det är ofta detta vi gärna vill prata jättemycket om vi själva är involverade i form av svår situation. Vi vill genompratta om att Anders eller Malin eller Vemner nu kan vara har agerat på ett vis...

**Slut:**
- Raw: Så ibland är det något så enkelt som ska till men nåt är igen. Vi missar ofta det här och vi bilder oss ofta en tolkning uppfattning av att  någon annan blockerar någonting vi vill eller ledningen blo...
- Enhanced: Så ibland är det något så enkelt som ska till men nåt är igen. Vi missar ofta detta och vi bildar oss ofta en tolkning uppfattning av att någon annan blockerar någonting vi vill eller ledningen blocke...

### faster_whisper small

**Början:**
- Raw: en sak. Vad är en konflikt egentligen....
- Enhanced: En sak. Vad är en konflikt egentligen....

**Mitten:**
- Raw: Jo, under där så ligger det just. Någon form av känsla av frustration, uppgivenhet och så vidare....
- Enhanced: Jo, under där så ligger det just. Någon form av känsla av frustration, uppgivenhet och så vidare....

**Slut:**
- Raw: Så ibland är det något så enkelt som ska till men återigen vi missar ofta det här  och vi bildar oss ofta en tolkning uppfattning av att någon annan  blockerar någonting vi vill eller ledningen blocke...
- Enhanced: Så ibland är det något så enkelt som ska till men återigen vi missar ofta detta och vi bildar oss ofta en tolkning uppfattning av att någon annan blockerar någonting vi vill eller ledningen blockerar ...

### whisper base

**Början:**
- Raw: En sak är en konflikt egentligen. Där finns det hur många olika definitioner som helst....
- Enhanced: En sak är en konflikt egentligen. Där finns det hur många olika definitioner som helst....

**Mitten:**
- Raw: Vad finns bakom ett frustrerad agerande i en konflikt. Ja, under där ligger det just....
- Enhanced: Vad finns bakom ett frustrerat agerande i en konflikt. Ja, under där ligger det just....

**Slut:**
- Raw: Eller ledningen blockerar någonting vi vill och det är inte alltid att det stämmer. Så här är det spännande upptäckter att göra.....
- Enhanced: Eller ledningen blockerar någonting vi vill och det är inte alltid att det stämmer. Så här är det spännande upptäckter att göra....

### whisper small

**Början:**
- Raw: en sak. Vad är en konflikt egentligen....
- Enhanced: En sak. Vad är en konflikt egentligen....

**Mitten:**
- Raw: Upplevd blockering. Det behöver inte vara....
- Enhanced: Upplevd blockering. Det behöver inte vara....

**Slut:**
- Raw: Så här är det spännande upptäckter att göra. Om man är nöjda.....
- Enhanced: Så här är det spännande upptäckter att göra. Om man är nöjda....


## Rekommendation

### Snabbast: faster_whisper base
- Tid: 15.2s
- CPU Peak: 687.8%
- RAM: 0.81GB

### Bäst kvalitet: whisper small
- Word Count: 1173
- Nonsense Ratio: 0.168
- Swedish Chars: 0.063

### Sweetspot (Rekommendation): faster_whisper base

**Anledning:**
- Balanserar hastighet (15.2s) och kvalitet (1150 ord, 0.174 nonsense ratio)
- CPU-användning: 687.8% peak, 515.1% medel
- Minne: 0.81GB
- Lämplig för demo: Acceptabel hastighet med bra kvalitet

---

*Genererad automatiskt från benchmark-resultat*
