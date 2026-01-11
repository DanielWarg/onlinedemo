# Fort Knox Local - Snabbstart Guide

## Snabb installation (5 minuter)

### Steg 1: Installera dependencies
```bash
cd fortknox-local
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Steg 2: Installera llama.cpp
```bash
./install_llama.sh
```

### Steg 3: Ladda ner modell
```bash
./download_model.sh
# Följ instruktionerna för att ladda ner modell från Hugging Face
```

### Steg 4: Starta tjänsterna

**Terminal 1 - llama.cpp server:**
```bash
./start_llama_server.sh
```

**Terminal 2 - Fort Knox Local:**
```bash
./start.sh
```

### Steg 5: Testa
```bash
curl http://localhost:8787/health
# Borde returnera: {"status":"ok","testmode":false}
```

## Test Mode (utan LLM)

För testning kan du köra med fasta fixtures:
```bash
FORTKNOX_TESTMODE=1 ./start.sh
```

## Konfigurera VPS

När Fort Knox Local körs:

1. Hämta din Tailscale IP:
   ```bash
   tailscale ip -4
   ```

2. Uppdatera `docker-compose.yml`:
   ```yaml
   FORTKNOX_REMOTE_URL: http://<tailscale-ip>:8787
   ```

3. Restart API:
   ```bash
   docker-compose restart api
   ```

## Felsökning

### llama-server hittas inte
```bash
# Kolla om installerat
brew list llama.cpp

# Eller lägg till i PATH om byggt från källa
export PATH=$PATH:$HOME/.local/llama.cpp/llama.cpp
```

### Ingen modell hittad
```bash
# Kolla modell directory
ls -la ~/.cache/fortknox/models/

# Ladda ner modell manuellt
cd ~/.cache/fortknox/models/
# Se download_model.sh för instruktioner
```

### Port redan används
```bash
# Ändra port i .env eller start-scriptet
FORTKNOX_PORT=8788 ./start.sh
```
