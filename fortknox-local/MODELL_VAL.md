# Modell-val för Fort Knox Local

## Modell-alternativ

Dokumentationen nämner: **Ministral-3-8B-Instruct-2512**

### Baseline: Mistral 7B Instruct v0.3 (Rekommenderat för v1)

**Fördelar:**
- ✅ GGUF finns direkt tillgänglig
- ✅ Fungerar med llama.cpp direkt
- ✅ Beprövad och stabil
- ✅ Bra kompatibilitet med alla llama.cpp-versioner

**Nedladdning:**
```bash
cd ~/.cache/fortknox/models
huggingface-cli download bartowski/Mistral-7B-Instruct-v0.3-GGUF \
  mistral-7b-instruct-v0.3.Q4_K_M.gguf \
  --local-dir . \
  --local-dir-use-symlinks False
```

**Rekommendation:** Använd denna för v1-stabilitet och beprövad kompatibilitet.

### Approved Upgrade Path: Ministral-3-8B-Instruct-2512 GGUF

**Fördelar:**
- ✅ Officiell GGUF-version finns nu
- ✅ Bättre prestanda än Mistral 7B
- ✅ Vision capabilities (8.4B language + 0.4B vision)
- ✅ 256K context window
- ✅ Apache 2.0 License

**Tillgängliga GGUF-versioner:**

1. **Officiell:** `mistralai/Ministral-3-8B-Instruct-2512-GGUF`
   - Officiell konvertering från Mistral AI
   - Rekommenderat för produktion

2. **Community (bartowski):** `bartowski/Ministral-3-8B-Instruct-2512-GGUF`
   - Känd för kvalitetskonverteringar
   - Olika quantization-alternativ

3. **Community (lmstudio-community):** `lmstudio-community/Ministral-3-8B-Instruct-2512-GGUF`
   - Optimerad för LM Studio/llama.cpp
   - Bra kompatibilitet

**Nedladdning (officiell):**
```bash
cd ~/.cache/fortknox/models
huggingface-cli download mistralai/Ministral-3-8B-Instruct-2512-GGUF \
  <filnamn>.gguf \
  --local-dir . \
  --local-dir-use-symlinks False
```

**Risknotis:**
- ⚠️ Kräver llama.cpp version som stödjer Ministral 3 arkitektur
- ⚠️ Verifiera llama.cpp-kompatibilitet innan produktionsanvändning
- ⚠️ Testa grundligt i testmiljö först

**Rekommendation:** Approved upgrade path efter v1-stabilisering. Verifiera llama.cpp-kompatibilitet innan produktionsanvändning.

## Rekommendation

**v1 (Nu):** Använd **Mistral 7B Instruct v0.3** (GGUF)
- Stabil och beprövad
- Fungerar med alla llama.cpp-versioner
- Ingen kompatibilitetsrisk

**v1.1+ (Framtida):** Uppgradera till **Ministral-3-8B-Instruct-2512 GGUF**
- Bättre prestanda
- Vision capabilities
- Efter verifiering av llama.cpp-kompatibilitet

## Uppdatera engine_id

När du väljer modell, uppdatera `engine_id` i Fort Knox:
- Mistral 7B: `mistral-7b-instruct-v0.3-gguf-q4_k_m`
- Ministral 3 8B: `ministral-3-8b-instruct-2512-gguf-q4_k_m`
