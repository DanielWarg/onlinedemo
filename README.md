## Arbetsytan

Arbetsytan är en säker intern arbetsmiljö för hantering av känsligt journalistiskt material.  
Systemet är byggt för att samla, strukturera och sammanställa information utan att riskera källskydd eller dataintegritet.

Arbetsytan utgår från principen att **originalmaterial aldrig ska exponeras i användargränssnittet**. Allt arbete sker i en **maskad vy**.

### Varför Arbetsytan?

I journalistiskt arbete hanteras ofta information som inte får läcka – vare sig genom misstag, tekniska genvägar eller externa tjänster.  
Arbetsytan är byggd för att visa hur man kan arbeta snabbt och strukturerat med känsligt material, samtidigt som säkerheten alltid är standard.

Systemet är konstruerat för att **hellre stoppa ett flöde än att chansa**.

### Vad gör Arbetsytan?

Arbetsytan är ett internt verktyg som:

- **Organiserar arbete i projekt**: allt material samlas i projekt för överblick, struktur och spårbarhet.
- **Samlar källmaterial**: dokument, textfiler, PDF:er och röstmemon kan laddas upp eller spelas in direkt.
- **Scout – import från feeds**: via Scout kan projekt skapas direkt från RSS/Atom‑flöden. Feed‑items importeras automatiskt som dokument, anteckningar och källor.
- **Sanerar innehåll automatiskt**: all text normaliseras och maskas innan den blir tillgänglig.
- **Visar alltid maskad vy**: användaren arbetar med sanerad text; originalmaterial exponeras aldrig i UI.
- **Transkriberar röstmemo lokalt**: tal‑till‑text sker lokalt utan externa tjänster.
- **Skapar säkra sammanställningar (Fort Knox)**: projektmaterial kan sammanställas till strukturerade rapporter med strikt integritetskontroll.

### Vad gör Arbetsytan inte?

- Publicerar innehåll eller fungerar som CMS
- Skriver artiklar eller producerar färdig journalistik
- Ersätter journalistens bedömning
- Exponerar rådata i användargränssnittet

### Hur används Arbetsytan?

1. **Skapa projekt** – manuellt eller via Scout (RSS/Atom).
2. **Tillför material** – ladda upp dokument, spela in röstmemon eller importera feed‑items.
3. **Automatisk sanering** – systemet maskar känsligt innehåll direkt.
4. **Arbeta i maskad vy** – materialet är säkert att läsa, analysera och strukturera.
5. **Sammanställ vid behov** – Fort Knox används för överblick och analys, inte för publicering.

### Fort Knox – säker sammanställning

Fort Knox är Arbetsytans modul för säker sammanställning av projektmaterial:

- Endast sanerat material används
- Sammanställning stoppas om något är osäkert (**fail‑closed**)
- Resultatet kontrolleras så att inga identifierare återskapas (re‑id guard)
- Samma underlag ger alltid samma rapport (idempotens/fingerprint)
- Rapporter kan sparas som dokument i projektet

Fort Knox används för analys och överblick, inte för kreativt skrivande.

### Säkerhet i korthet

- **Security by default** – säkerhet är alltid på
- **Fail‑closed** – vid osäkerhet stoppas flödet
- **Ingen rådata i loggar eller UI** (metadata‑only)
- **Skydd mot osäkra feeds och nätverksanrop** (SSRF‑skydd)

### Default: allt kör lokalt (opt‑in OpenAI för demo)

- **Tal‑till‑text (STT)** körs lokalt i API:t som default (`STT_ENGINE=faster_whisper`, `WHISPER_MODEL=small`). För demo kan du byta till OpenAI med `STT_ENGINE=openai` + `OPENAI_API_KEY` (samt ev. `OPENAI_STT_MODEL`).
- **Fort Knox (LLM)** körs lokalt som default via `fortknox-local/` + `llama.cpp`. För demo kan du använda OpenAI via LangChain-endpointen (`FORTKNOX_PIPELINE=langchain`, `FORTKNOX_LC_PROVIDER=openai`, `OPENAI_API_KEY`).
- **Inga secrets i repo**: lägg nycklar i `.env` (gitignored).
- **Om du exponerar UI:t via Tailscale Funnel** så är det bara en HTTPS‑tunnel *till din Mac* (för demo/åtkomst).

### Teknik (översikt)

- **Backend**: FastAPI + PostgreSQL
- **Frontend**: React + Vite
- **Tal‑till‑text**: lokal `faster-whisper` (default) eller OpenAI (opt-in)
- **Fort Knox LLM**: lokal `llama.cpp` (default) eller OpenAI via LangChain (opt-in)
- **Deployment**: Docker Compose

### Starta lokalt

```bash
make dev
```

Öppna:
- `http://localhost:3000`

### Sammanfattning

Arbetsytan visar hur säkra, interna verktyg kan byggas för journalistiskt arbete där integritet, spårbarhet och tydliga gränser är viktigare än snabb publicering.

### För arbetsgivare (snabb överblick)

- **One‑pager (arkitektur + dataflöde + hotbild + fail‑closed + “produktion vs demo”)**: `ONEPAGER.md`

### Mer (om du vill läsa vidare)

- Fort Knox/arkitektur: `docs/ARCHITECTURE.md`, `docs/FLOWS.md`
- Säkerhet: `SECURITY_MODEL.md`, `docs/SECURITY.md`
- Deploy (Tailscale Funnel/Caddy): `deploy/tailscale/README.md`

