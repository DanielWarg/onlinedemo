# Fort Knox Local - Start Guide

## Snabbstart (när modell är nedladdad)

### Terminal 1 - llama.cpp server:
```bash
cd fortknox-local
./start_llama_server.sh
```

### Terminal 2 - Fort Knox Local:
```bash
cd fortknox-local
./start.sh
```

### Testa:
```bash
curl http://localhost:8787/health
# Borde returnera: {"status":"ok","testmode":false}
```

## Test Mode (utan LLM)

Om du vill testa utan att ladda ner modell:
```bash
cd fortknox-local
FORTKNOX_TESTMODE=1 ./start.sh
```

## Stoppa tjänsterna

```bash
# Stoppa Fort Knox Local
pkill -f "python3 main.py"

# Stoppa llama.cpp server
pkill -f "llama-server"
```

## Felsökning

### Port redan används
```bash
# Ändra port i .env
FORTKNOX_PORT=8788 ./start.sh
```

### Modell hittas inte
```bash
# Kolla modell directory
ls -la ~/.cache/fortknox/models/

# Ladda ner modell
cd ~/.cache/fortknox/models
./download_mistral.sh
```

### llama-server hittas inte
```bash
# Kolla installation
which llama-server

# Om inte hittad, lägg till i PATH
export PATH=$PATH:/opt/homebrew/bin
```
