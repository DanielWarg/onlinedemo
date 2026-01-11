# DEMO_NARRATIVE.md

Låsta formuleringar för demo och UI. Alla texter i UI ska kopieras verbatim från denna fil.

---

## 1. Originalhantering (kritisk)

**Formulering:**
```
Originalmaterial bevaras i säkert lager och exponeras aldrig i arbetsytan.
```

**Användning:**
- Tooltip/hjälptext i DocumentView bredvid "Maskad vy"

---

## 2. Maskad vy – huvudtext

**Formulering:**
```
Maskad vy
```

**Användning:**
- DocumentView header (behålls som nu)

---

## 3. Maskad vy – förklaring

**Formulering:**
```
All känslig information är automatiskt maskerad. Originalmaterial exponeras aldrig.
```

**Användning:**
- Tooltip/hjälptext i DocumentView bredvid "Maskad vy"

---

## 4. Saneringsnivå – Normal

**Formulering:**
```
Normal: Standard sanering. Email, telefonnummer och personnummer maskeras automatiskt.
```

**Användning:**
- Tooltip på saneringsnivå badge i ProjectDetail material list (när sanitize_level = "normal")

---

## 5. Saneringsnivå – Strikt

**Formulering:**
```
Strikt: Ytterligare numeriska sekvenser maskeras för extra säkerhet.
```

**Användning:**
- Tooltip på saneringsnivå badge i ProjectDetail material list (när sanitize_level = "strict")

---

## 6. Saneringsnivå – Paranoid

**Formulering:**
```
Paranoid: Alla siffror och känsliga mönster maskeras. AI och export avstängda för maximal säkerhet.
```

**Användning:**
- Tooltip på saneringsnivå badge i ProjectDetail material list (när sanitize_level = "paranoid")

---

## 7. AI avstängt – huvudtext

**Formulering:**
```
AI avstängt
```

**Användning:**
- ProjectDetail material list (behålls som nu)

---

## 8. AI avstängt – förklaring

**Formulering:**
```
Dokumentet krävde paranoid sanering. AI-funktioner är avstängda för säkerhet.
```

**Användning:**
- Tooltip/hjälptext i ProjectDetail bredvid "AI avstängt"

---

## 9. Klassificering – förklaring

**Formulering:**
```
Klassificering påverkar åtkomst, loggning och export enligt säkerhetsmodellen.
```

**Användning:**
- CreateProject form (behålls som nu)

---

## Regler

- Alla UI-texter ska kopieras verbatim från denna fil
- Inga variationer eller improvisationer tillåtna
- Om en formulering behöver ändras, uppdatera denna fil först, sedan UI

