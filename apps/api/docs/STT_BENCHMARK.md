# STT Benchmark Matrix - Prestanda & Kvalitet

## Översikt

Jämförelse mellan Whisper och faster-whisper med base/small modeller.

## Resultat

| Engine | Model | Run 1 (s) | Run 2 (s) | Avg (s) | CPU Peak (%) | CPU Avg (%) | RAM Peak (GB) | Word Count | Nonsense Ratio | Swedish Chars |
|--------|-------|-----------|-----------|---------|--------------|-------------|---------------|------------|----------------|---------------|
| whisper | base | 83.5 | 85.2 | 84.3 | 923.7 | 0.0 | 0.00 | 500 | 0.050 | 0.000 |

## Kvalitetsjämförelse (Snippets)

### whisper base

**Början:**
- Raw: N/A...
- Enhanced: N/A...

**Mitten:**
- Raw: N/A...
- Enhanced: N/A...

**Slut:**
- Raw: N/A...
- Enhanced: N/A...


## Rekommendation

### Snabbast: whisper base
- Tid: 84.3s
- CPU Peak: 923.7%
- RAM: 0.00GB

### Bäst kvalitet: whisper base
- Word Count: 500
- Nonsense Ratio: 0.050
- Swedish Chars: 0.000

### Sweetspot (Rekommendation): whisper base

**Anledning:**
- Balanserar hastighet (84.3s) och kvalitet (500 ord, 0.050 nonsense ratio)
- CPU-användning: 923.7% peak, 0.0% medel
- Minne: 0.00GB
- Lämplig för demo: Acceptabel hastighet med bra kvalitet

---

*Genererad automatiskt från benchmark-resultat*
