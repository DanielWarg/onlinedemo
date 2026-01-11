ARCHIVED: replaced by docs/ARCHITECTURE.md, docs/FLOWS.md, docs/VERIFYING.md

# Fort Knox - Produktionssetup Guide

Detta dokument beskriver hur du gör Fort Knox produktionsredo.

## Översikt

Fort Knox består av två delar:
1. **VPS Backend** (redan implementerat) - API som bygger pack och skickar till Mac
2. **Fort Knox Local** (ny) - LLM-service på din Mac som processar pack

## Del 1: Fort Knox Local på Mac

### Steg 1: Installera Dependencies

```bash
cd fortknox-local
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Steg 2: Installera llama.cpp Server

**Via Homebrew (enklast):**
```bash
brew install llama.cpp
```

**Eller bygg från källa:**
```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
make
export PATH=$PATH:$(pwd)
```

### Steg 3: Ladda ner LLM Model

Rekommenderat: Ministral 7B Instruct v0.3 (GGUF format, Q4_K_M quantization)

```bash
mkdir -p ~/.cache/fortknox/models
cd ~/.cache/fortknox/models

# Ladda ner från Hugging Face (exempel)
# Se: https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF
# Ladda ner: mistral-7b-instruct-v0.3.Q4_K_M.gguf
```

**Alternativ: Mindre modell för testning**
```bash
# Phi-3 Mini (3.8B) - snabbare men sämre kvalitet
# Se: https://huggingface.co/bartowski/Phi-3-mini-4k-instruct-GGUF
```

### Steg 4: Starta llama.cpp Server

```bash
# Om installerat via Homebrew
llama-server \
  -m ~/.cache/fortknox/models/mistral-7b-instruct-v0.3.Q4_K_M.gguf \
  --port 8080 \
  --ctx-size 4096 \
  --n-predict 2048 \
  --threads 4

# Eller om byggt från källa
./llama-server \
  -m ~/.cache/fortknox/models/mistral-7b-instruct-v0.3.Q4_K_M.gguf \
  --port 8080 \
  --ctx-size 4096 \
  --n-predict 2048 \
  --threads 4
```

**Tips:**
- `--threads 4` anpassa till dina CPU-kärnor
- `--ctx-size` = kontextstorlek (högre = mer minne)
- `--n-predict` = max tokens i output

### Steg 5: Konfigurera Fort Knox Local

```bash
cd fortknox-local
cp .env.example .env
```

Redigera `.env`:
```
LLAMA_SERVER_URL=http://localhost:8080
FORTKNOX_PORT=8787
LOG_LEVEL=INFO
FORTKNOX_TESTMODE=0
```

### Steg 6: Starta Fort Knox Local

```bash
source venv/bin/activate
python main.py
```

Service startar på `http://localhost:8787`

Testa:
```bash
curl http://localhost:8787/health
# Borde returnera: {"status":"ok","testmode":false}
```

### Steg 7: Exponera via Tailscale

1. **Installera Tailscale** (om inte redan gjort):
   ```bash
   brew install tailscale
   sudo tailscale up
   ```

2. **Hämta din Tailscale IP:**
   ```bash
   tailscale ip -4
   # Exempel: 100.64.1.2
   ```

3. **Fort Knox Local lyssnar redan på 0.0.0.0:8787** (alla interfaces)
   - Det betyder att den redan är tillgänglig via Tailscale!

4. **Testa från VPS:**
   ```bash
   # Från din VPS
   curl http://<tailscale-ip>:8787/health
   # Borde returnera: {"status":"ok","testmode":false}
   ```

## Del 2: Konfigurera VPS

### Steg 1: Uppdatera docker-compose.yml

Lägg till/uppdatera environment variables:

```yaml
services:
  api:
    environment:
      # ... existing vars ...
      FORTKNOX_REMOTE_URL: http://<tailscale-ip>:8787
      FORTKNOX_TESTMODE: 0
```

**Exempel:**
```yaml
FORTKNOX_REMOTE_URL: http://100.64.1.2:8787
FORTKNOX_TESTMODE: 0
```

### Steg 2: Restart API

```bash
docker-compose restart api
```

### Steg 3: Verifiera

```bash
# Testa att VPS kan nå Fort Knox Local
docker-compose exec api curl http://<tailscale-ip>:8787/health
```

## Del 3: Frontend (UI)

API-endpoints finns redan:
- `POST /api/fortknox/compile` - Skapa rapport
- `GET /api/projects/{project_id}/fortknox/reports` - Lista rapporter
- `GET /api/fortknox/reports/{report_id}` - Hämta specifik rapport

**Frontend implementation behöver:**
1. Knapp "Skapa Fort Knox-rapport" i projektvyn
2. Modal/Dialog med:
   - Dropdown: Policy (Intern/Extern)
   - Dropdown: Mall (Weekly/Brief/Incident)
   - Knapp: "Kompilera"
3. Status-visning (Kompilerar... / Klar / Fel)
4. Rapport-vyn (Markdown preview + export/copy)

**Exempel API-anrop:**

```typescript
// Skapa rapport
const response = await fetch(`/api/fortknox/compile`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    project_id: 1,
    policy_id: 'internal', // eller 'external'
    template_id: 'weekly' // eller 'brief', 'incident'
  })
});

// Lista rapporter
const reports = await fetch(`/api/projects/${projectId}/fortknox/reports`);

// Hämta specifik rapport
const report = await fetch(`/api/fortknox/reports/${reportId}`);
```

## Del 4: Testning

### Test Mode (utan LLM)

För testning kan du köra med fasta fixtures:

**Fort Knox Local:**
```bash
FORTKNOX_TESTMODE=1 python main.py
```

**VPS:**
```yaml
FORTKNOX_TESTMODE: 1
```

**Kör verifiering:**
```bash
make verify-fortknox-v1
```

### Produktion

När allt fungerar:
```yaml
FORTKNOX_TESTMODE: 0
```

## Felsökning

### Fort Knox Local kan inte nå llama.cpp server

```bash
# Kolla att llama-server körs
ps aux | grep llama-server

# Testa manuellt
curl http://localhost:8080/completion -X POST -d '{"prompt":"test","n_predict":10}'
```

### VPS kan inte nå Fort Knox Local

```bash
# Från Mac: Kolla Tailscale status
tailscale status

# Från VPS: Testa ping
ping <tailscale-ip>

# Testa curl
curl http://<tailscale-ip>:8787/health
```

### LLM returnerar invalid JSON

- Kolla logs i Fort Knox Local
- Öka `n_predict` i llama.cpp server
- Testa med större/mindre model

### Timeout errors

- Öka timeout i `fortknox_remote.py` (default 30s)
- Kolla llama.cpp server logs för långsamma requests
- Överväg mindre model eller färre threads

## Säkerhet

1. **Tailscale:** Fort Knox Local bör endast vara tillgänglig via Tailscale
2. **Firewall:** Begränsa port 8787 till Tailscale IPs (valfritt)
3. **Logging:** Fort Knox Local loggar aldrig textinnehåll, bara metadata
4. **HTTPS:** Överväg TLS/HTTPS för Fort Knox Local (kräver reverse proxy)

## Nästa steg

1. Implementera Frontend UI-komponenter
2. Lägg till mer avancerad error handling
3. Lägg till rate limiting (valfritt)
4. Överväg caching av rapporter (redan idempotent)
