ARCHIVED: replaced by docs/ARCHITECTURE.md, docs/FLOWS.md, docs/VERIFYING.md

# Fort Knox Local - Status

## ✅ Installation Komplett

- **Modell:** Ministral-3-8B-Instruct-2512-Q4_K_M.gguf (4.8GB)
- **llama.cpp:** Installerat via Homebrew
- **Fort Knox Local:** Körs på port 8787
- **Health Check:** ✅ OK

## Tjänster

### Fort Knox Local
- **Status:** ✅ Körs
- **Port:** 8787
- **Test Mode:** False (använder riktig LLM)
- **Health:** http://localhost:8787/health

### llama.cpp Server
- **Status:** ⚠️ Verifiera att den körs
- **Port:** 8080
- **Start:** `./start_llama_server.sh`

## Nästa Steg

1. **Verifiera llama.cpp server körs:**
   ```bash
   curl http://localhost:8080
   # Borde ge något svar (eller 404, men server körs)
   ```

2. **Installera Tailscale** (för remote access):
   ```bash
   # Installera från: https://tailscale.com/download
   tailscale up
   ```

3. **Konfigurera VPS:**
   - Hämta Tailscale IP: `tailscale ip -4`
   - Uppdatera `docker-compose.yml` med `FORTKNOX_REMOTE_URL`
   - Restart API: `docker-compose restart api`

## Testa Fort Knox

När båda tjänsterna körs och VPS är konfigurerad:

```bash
# Från VPS eller lokalt
curl http://localhost:8000/api/fortknox/compile \
  -X POST \
  -H "Content-Type: application/json" \
  -u admin:password \
  -d '{
    "project_id": 1,
    "policy_id": "internal",
    "template_id": "weekly"
  }'
```
