# Starta Fort Knox Local

## Snabbstart

### Terminal 1 - llama.cpp server:
```bash
cd fortknox-local
./start_llama_server.sh
```

Vänta tills du ser: "llama server listening at http://0.0.0.0:8080"

### Terminal 2 - Fort Knox Local:
```bash
cd fortknox-local
./start.sh
```

Vänta tills du ser: "Uvicorn running on http://0.0.0.0:8787"

## Verifiera att allt fungerar

### Test 1: Health check
```bash
curl http://localhost:8787/health
# Borde returnera: {"status":"ok","testmode":false}
```

### Test 2: llama.cpp server
```bash
curl http://localhost:8080/health
# Borde returnera OK (eller 404 om health endpoint saknas, men server körs)
```

### Test 3: Fullständig test
```bash
cd fortknox-local
./test_connection.sh
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

# Verifiera att modellen finns
find ~/.cache/fortknox/models -name "*.gguf"
```

### llama-server hittas inte
```bash
# Kolla installation
which llama-server

# Om inte hittad, lägg till i PATH
export PATH=$PATH:/opt/homebrew/bin
```

## Nästa steg: Konfigurera VPS

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
