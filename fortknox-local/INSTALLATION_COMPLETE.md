# ✅ Fort Knox Local - Installation Komplett

## Status

✅ **Modell nedladdad:** Ministral-3-8B-Instruct-2512-Q4_K_M.gguf (4.8GB)
✅ **llama.cpp installerat:** /opt/homebrew/bin/llama-server
✅ **Fort Knox Local konfigurerad:** Alla scripts redo
✅ **Dependencies installerade:** Python packages OK

## Starta Tjänsterna

### Steg 1: Starta llama.cpp server (Terminal 1)

```bash
cd fortknox-local
./start_llama_server.sh
```

**Vänta tills du ser:**
```
llama server listening at http://0.0.0.0:8080
```

Detta kan ta 30-60 sekunder första gången (modell laddas in minnet).

### Steg 2: Starta Fort Knox Local (Terminal 2)

**Öppna ett NYTT terminalfönster** och kör:

```bash
cd fortknox-local
./start.sh
```

**Vänta tills du ser:**
```
Uvicorn running on http://0.0.0.0:8787
```

## Verifiera Installation

### Test 1: Health Check
```bash
curl http://localhost:8787/health
```
**Förväntat svar:**
```json
{"status":"ok","testmode":false}
```

### Test 2: Fullständig Test
```bash
cd fortknox-local
./test_connection.sh
```

## Konfigurera VPS (När Tailscale är installerat)

### Steg 1: Hämta Tailscale IP
```bash
tailscale ip -4
# Exempel output: 100.64.1.2
```

### Steg 2: Uppdatera docker-compose.yml

Lägg till/uppdatera i `docker-compose.yml`:
```yaml
services:
  api:
    environment:
      FORTKNOX_REMOTE_URL: http://100.64.1.2:8787  # Ersätt med din Tailscale IP
```

### Steg 3: Restart API
```bash
docker-compose restart api
```

## Stoppa Tjänsterna

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

### llama-server hittas inte
```bash
# Verifiera installation
which llama-server
# Borde visa: /opt/homebrew/bin/llama-server
```

### Modell hittas inte
```bash
# Verifiera modell
ls -lh ~/.cache/fortknox/models/*.gguf
# Borde visa: Ministral-3-8B-Instruct-2512-Q4_K_M.gguf (4.8G)
```

## Nästa Steg

1. ✅ Modell nedladdad
2. ⏳ Starta tjänsterna (2 terminaler)
3. ⏳ Installera Tailscale (för remote access)
4. ⏳ Konfigurera VPS med Tailscale IP
5. ⏳ Testa Fort Knox från VPS

## Dokumentation

- `START_FORTKNOX.md` - Detaljerade start-instruktioner
- `MODELL_VAL.md` - Modell-information och rekommendationer
- `README.md` - Fullständig dokumentation
- `QUICKSTART.md` - Snabbstart guide
