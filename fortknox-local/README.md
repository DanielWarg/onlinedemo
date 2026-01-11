# Fort Knox Local - LLM Service på Mac

Fort Knox Local är den lokala LLM-tjänsten som körs på din Mac och processar KnoxInputPack till rapporter.

## Snabbstart

```bash
# 1. Installera dependencies
cd fortknox-local
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Installera llama.cpp (automatiskt)
./install_llama.sh

# 3. Ladda ner modell (se instruktioner i scriptet)
./download_model.sh

# 4. Starta llama.cpp server (i ett terminalfönster)
./start_llama_server.sh

# 5. Starta Fort Knox Local (i ett annat terminalfönster)
./start.sh
```

## Detaljerad Setup

### 1. Installera Dependencies

```bash
cd fortknox-local
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Installera llama.cpp Server

Kör install-scriptet:
```bash
./install_llama.sh
```

Detta installerar via Homebrew om möjligt, annars bygger från källa.

### 3. Ladda ner LLM Model

Kör download-scriptet för instruktioner:
```bash
./download_model.sh
```

Rekommenderat: Mistral 7B Instruct v0.3 (Q4_K_M quantization)
- Ladda ner från: https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF
- Spara i: `~/.cache/fortknox/models/`

### 4. Starta llama.cpp Server

```bash
./start_llama_server.sh [port] [threads]
# Default: port 8080, threads 4
```

### 5. Konfigurera Fort Knox Local

`.env` filen skapas automatiskt från `.env.example`. Redigera om behövs:
```
LLAMA_SERVER_URL=http://localhost:8080
FORTKNOX_PORT=8787
LOG_LEVEL=INFO
FORTKNOX_TESTMODE=0
```

### 6. Starta Fort Knox Local

```bash
./start.sh
```

Service startar på `http://localhost:8787`

### 7. Exponera via Tailscale

1. Installera Tailscale på Mac om inte redan gjort
2. Hämta din Tailscale IP: `tailscale ip -4`
3. Fort Knox Local lyssnar på `0.0.0.0:8787` (alla interfaces)
4. I VPS docker-compose.yml, sätt:
   ```yaml
   FORTKNOX_REMOTE_URL=http://<tailscale-ip>:8787
   ```

## Användning

Fort Knox Local tar emot POST requests på `/compile`:

```bash
curl -X POST http://localhost:8787/compile \
  -H "Content-Type: application/json" \
  -d @test_pack.json
```

Response är JSON enligt `KnoxLLMResponse` schema.

## Utveckling

För testning kan du köra med fast fixtures istället för LLM:
```bash
FORTKNOX_TESTMODE=1 python main.py
```

## Säkerhet

- Fort Knox Local loggar **aldrig** textinnehåll, bara metadata
- Rekommenderat: Kör bakom Tailscale (privat nätverk)
- Rekommenderat: Använd firewall för att endast tillåta Tailscale IPs
