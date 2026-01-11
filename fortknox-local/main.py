#!/usr/bin/env python3
"""
Fort Knox Local - LLM Service på Mac

Tar emot KnoxInputPack från VPS, kör lokal LLM (via llama.cpp server),
och returnerar strikt JSON enligt KnoxLLMResponse schema.

Säkerhet: Loggar aldrig textinnehåll, bara metadata.
"""
import os
import json
import logging
import re
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
import uvicorn
import requests

# Setup logging (metadata-only, ingen textinnehåll)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Fort Knox Local", version="1.0.0")

# CORS (endast för development, i produktion använd Tailscale)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # I produktion: begränsa till Tailscale IPs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://localhost:8080")
FORTKNOX_PORT = int(os.getenv("FORTKNOX_PORT", "8787"))
TESTMODE = os.getenv("FORTKNOX_TESTMODE", "0") == "1"
FORTKNOX_MAX_ITEM_CHARS = int(os.getenv("FORTKNOX_MAX_ITEM_CHARS", "2000"))

# Schemas (måste matcha apps/api/schemas.py)
class KnoxPolicyInput(BaseModel):
    policy_id: str
    policy_version: str
    ruleset_hash: str
    mode: str  # "internal" | "external"
    sanitize_min_level: str
    quote_limit_words: int
    date_strictness: str

class DocumentItem(BaseModel):
    id: int
    text: str

class NoteItem(BaseModel):
    id: int
    text: str

class CompileRequest(BaseModel):
    policy: KnoxPolicyInput
    template_id: str
    input_fingerprint: str
    documents: list[DocumentItem]
    notes: list[NoteItem]

class KnoxLLMResponse(BaseModel):
    template_id: str
    language: str = "sv"
    title: str
    executive_summary: str
    themes: list[Dict[str, Any]]  # [{"name": str, "bullets": list[str]}]
    timeline_high_level: list[str]
    risks: list[Dict[str, Any]]  # [{"risk": str, "mitigation": str}]
    open_questions: list[str]
    next_steps: list[str]
    confidence: str  # "low" | "medium" | "high"


# Test fixtures (för deterministisk testning)
TEST_FIXTURES = {
    "internal": {
        "template_id": "weekly",
        "language": "sv",
        "title": "Intern Rapport - Vecka 1",
        "executive_summary": "Detta är en sammanfattning av interna händelser.",
        "themes": [
            {"name": "Säkerhet", "bullets": ["Ökad övervakning", "Nya protokoll"]}
        ],
        "timeline_high_level": ["Vecka 1: Incident A", "Vecka 2: Åtgärd B"],
        "risks": [
            {"risk": "Dataintrång", "mitigation": "Förbättrad kryptering"}
        ],
        "open_questions": ["Vad hände med servern?"],
        "next_steps": ["Granska loggar"],
        "confidence": "high"
    },
    "external": {
        "template_id": "weekly",
        "language": "sv",
        "title": "Extern Sammanfattning",
        "executive_summary": "En översiktlig sammanfattning för extern användning.",
        "themes": [],
        "timeline_high_level": [],
        "risks": [],
        "open_questions": [],
        "next_steps": [],
        "confidence": "medium"
    }
}


def call_llama_server(prompt: str, *, temperature: float = 0.2, n_predict: int = 2048) -> str:
    """
    Anropa llama.cpp server för LLM-inferens.
    
    Args:
        prompt: Text prompt för LLM
    
    Returns:
        LLM response text
    """
    try:
        # llama.cpp server API (completion endpoint)
        response = requests.post(
            f"{LLAMA_SERVER_URL}/completion",
            json={
                "prompt": prompt,
                # Mer deterministiskt + mindre risk för trunkering
                "n_predict": n_predict,
                "temperature": temperature,
                # Undvik stop på "\n\n\n" då modellen ofta skriver nya rader i JSON och kan trunkeras.
                "stop": ["</s>"]
            },
            # Lokala modeller kan ta tid, särskilt när kontexten är stor.
            timeout=180
        )
        response.raise_for_status()
        data = response.json()
        return data.get("content", "")
    except requests.exceptions.RequestException as e:
        logger.error(f"llama.cpp server error: {e}")
        raise HTTPException(status_code=503, detail="LLM server unavailable")


def build_prompt(request: CompileRequest, documents_text: str, notes_text: str) -> str:
    """
    Bygg prompt för LLM baserat på policy och template.
    """
    mode = request.policy.mode
    template = request.template_id
    
    if mode == "internal":
        mode_instruction = "Intern redaktionell brief (kan innehålla mer detaljer, men inga personuppgifter)."
    else:
        mode_instruction = (
            "Extern redaktionell brief. Regler: "
            "INTE exakta datum/klockslag (använd 'i början av månaden', 'under veckan', etc), "
            "INTE långa citat från källan (>8 ord i följd), "
            "INTE personuppgifter eller identifierande detaljer. "
            "Skriv som en erfaren redaktör: konkret, journalistiskt, utan att prata om 'tester', 'system' eller 'confidentialitetshantering'."
        )
    
    anti_quote = ""
    if mode == "external":
        anti_quote = (
            "\nANTI-CITAT (KRITISKT):\n"
            "- Du får INTE kopiera meningar eller fraser från underlaget.\n"
            "- Du får inte återge 8+ ord i följd som förekommer i input.\n"
            "- Använd inga citattecken och inga blockcitat.\n"
            "- Parafrasera alltid och håll formuleringar generiska.\n"
        )
    
    prompt = f"""Du är en senior grävredaktör som skapar en strukturerad brief från ett journalistiskt projekt.

Policy: {mode_instruction}
Template: {template}
Språk: Svenska
{anti_quote}

Dokument:
{documents_text}

Noter:
{notes_text}

Skapa en rapport enligt följande JSON-struktur (svara ENDAST med JSON, ingen annan text):

{{
  "template_id": "{template}",
  "language": "sv",
  "title": "Titel på rapporten",
  "executive_summary": "Kort sammanfattning (2-3 meningar)",
  "themes": [
    {{"name": "Tema (t.ex. 'Påstående', 'Konsekvens', 'Kontext')", "bullets": [
      "Fakta: ...",
      "Vinkel: ...",
      "Verifiera: ...",
      "Kontaktlista: (myndighet/organisation/roll, inga namn)"
    ]}}
  ],
  "timeline_high_level": ["Relativ tid + händelse (ingen exakt datum/tid)", "Relativ tid + händelse"],
  "risks": [
    {{"risk": "Publiceringsrisk (juridik/etik/fakta)", "mitigation": "Hur vi minimerar risken"}}
  ],
  "open_questions": ["Vilket centralt påstående saknar vi primärkälla för?", "Vilken motpart måste vi kontakta innan publicering?"],
  "next_steps": ["Exakt 3 steg: vem/roll + vad + varför (utan PII)"],
  "confidence": "low|medium|high"
}}

JSON:"""
    
    return prompt


def parse_llm_response(llm_text: str, template_id: str) -> Dict[str, Any]:
    """
    Parse LLM response till JSON och validera.
    
    Args:
        llm_text: Raw LLM output
        template_id: Template ID
    
    Returns:
        Dict med KnoxLLMResponse data
    """
    # Försök extrahera JSON från response
    llm_text = llm_text.strip()
    
    # Ta bort markdown code blocks om de finns
    if "```json" in llm_text:
        llm_text = llm_text.split("```json")[1].split("```")[0].strip()
    elif "```" in llm_text:
        llm_text = llm_text.split("```")[1].split("```")[0].strip()
    
    # Försök hitta JSON object
    start_idx = llm_text.find("{")
    end_idx = llm_text.rfind("}") + 1
    
    if start_idx == -1 or end_idx == 0:
        raise ValueError("No JSON found in LLM response")
    
    json_str = llm_text[start_idx:end_idx]
    
    def _normalize_response_shape(data: Dict[str, Any]) -> Dict[str, Any]:
        # Fort Knox v1: next_steps ska vara list[str]. Modeller tenderar att returnera list[dict].
        ns = data.get("next_steps")
        if isinstance(ns, list):
            normalized: list[str] = []
            for item in ns:
                if isinstance(item, str):
                    normalized.append(item)
                    continue
                if isinstance(item, dict):
                    who = item.get("who") or item.get("role") or item.get("owner")
                    what = item.get("what") or item.get("action")
                    why = item.get("why") or item.get("reason")
                    parts = [p for p in [who, what, why] if isinstance(p, str) and p.strip()]
                    if parts:
                        normalized.append(" – ".join(parts))
                    else:
                        # Sista utväg: serialisera deterministiskt (utan att logga innehåll).
                        normalized.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
                    continue
                # Okänd typ -> str()
                normalized.append(str(item))
            data["next_steps"] = normalized
        return data

    try:
        data = json.loads(json_str)
        # Sätt template_id om det saknas
        if "template_id" not in data:
            data["template_id"] = template_id
        return _normalize_response_shape(data)
    except json.JSONDecodeError as e:
        # Showreel-säkert: logga aldrig råtext. Logga endast metadata.
        digest = hashlib.sha256(json_str.encode("utf-8", errors="ignore")).hexdigest()[:16]
        logger.error(f"JSON parse error: {e} (len={len(json_str)}, sha256_16={digest})")

        # Försök reparera vanliga JSON-fel från LLM:
        # - Saknad komma mellan värde och nästa fält/element (t.ex. ..."confidence":"high"\n"next_steps":...).
        # - Trailing commas före } eller ].
        def _repair_missing_commas(s: str) -> str:
            out: list[str] = []
            in_str = False
            esc = False
            depth = 0
            last_non_ws: Optional[str] = None

            for ch in s:
                if not in_str and ch == '"':
                    # Om vi är inne i en container och senaste token ser ut att vara ett värde,
                    # och nästa token börjar direkt med en sträng => saknad komma.
                    if depth > 0 and last_non_ws and last_non_ws not in "{[,:":  # already separated?
                        if last_non_ws in ('}', ']', '"') or last_non_ws.isdigit() or last_non_ws in ("e", "E", "l"):
                            out.append(',')
                out.append(ch)

                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\\\':
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch in "{[":
                        depth += 1
                    elif ch in "}]":
                        depth = max(0, depth - 1)

                if not in_str and ch not in " \\t\\r\\n":
                    last_non_ws = ch

            return "".join(out)

        repaired = _repair_missing_commas(json_str)
        # Ta bort trailing commas före } eller ]
        repaired = re.sub(r",(\\s*[}\\]])", r"\\1", repaired)

        try:
            data = json.loads(repaired)
            if "template_id" not in data:
                data["template_id"] = template_id
            logger.info("JSON repaired successfully", extra={"sha256_16": digest})
            return _normalize_response_shape(data)
        except json.JSONDecodeError as e2:
            logger.error(f"JSON repair failed: {e2} (sha256_16={digest})")
            raise ValueError(f"Invalid JSON from LLM: {e}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "testmode": TESTMODE}


@app.post("/compile", response_model=KnoxLLMResponse)
async def compile_report(request: CompileRequest):
    """
    Kompilera Fort Knox-rapport från KnoxInputPack.
    
    Säkerhet: Loggar aldrig textinnehåll, bara metadata.
    """
    start_time = datetime.now()
    
    # Log metadata only (aldrig textinnehåll)
    logger.info(
        "Compile request received",
        extra={
            "policy_id": request.policy.policy_id,
            "template_id": request.template_id,
            "input_fingerprint": request.input_fingerprint,
            "document_count": len(request.documents),
            "note_count": len(request.notes)
        }
    )
    
    # Test mode: returnera fast fixture
    if TESTMODE:
        logger.info(f"TESTMODE: Using fixture for {request.policy.mode}")
        fixture_key = "internal" if request.policy.mode == "internal" else "external"
        fixture_data = TEST_FIXTURES[fixture_key].copy()
        fixture_data["template_id"] = request.template_id
        
        try:
            return KnoxLLMResponse(**fixture_data)
        except ValidationError as e:
            logger.error(f"Fixture validation failed: {e}")
            raise HTTPException(status_code=500, detail="Test fixture validation failed")
    
    # Build prompt (bounded input för stabilitet + mindre risk för context-trunkering).
    # OBS: input är redan maskad/sanerad innan den når Fort Knox Local.
    def _clip(s: str) -> str:
        if not s:
            return ""
        if len(s) <= FORTKNOX_MAX_ITEM_CHARS:
            return s
        return s[:FORTKNOX_MAX_ITEM_CHARS] + "\n\n[TRUNCATED]"

    documents_text = "\n\n".join([f"[Dokument {doc.id}]\n{_clip(doc.text)}" for doc in request.documents])
    notes_text = "\n\n".join([f"[Not {note.id}]\n{_clip(note.text)}" for note in request.notes])
    
    try:
        prompt = build_prompt(request, documents_text, notes_text)

        # Call LLM (med retry om modellen spottar ur sig invalid JSON)
        last_err: Optional[Exception] = None
        for attempt in range(2):
            # Försök 1: ganska deterministiskt
            # Försök 2: maximalt deterministiskt + extra "valid JSON"-påminnelse
            if request.policy.mode == "external":
                temperature = 0.1 if attempt == 0 else 0.0
            else:
                temperature = 0.2 if attempt == 0 else 0.1
            retry_prompt = prompt
            if attempt == 1:
                retry_prompt = (
                    prompt
                    + "\n\nVIKTIGT: Du MÅSTE svara med VALID JSON som går att json.parse:a. "
                      "Inga kommentarer, inga trailing commas, inga radbrytningar i strängar. "
                      "Om du är osäker: returnera en minimal JSON enligt schemat med tomma listor.\n"
                )

            llm_response_text = call_llama_server(retry_prompt, temperature=temperature, n_predict=2048)

            try:
                response_data = parse_llm_response(llm_response_text, request.template_id)
                llm_response = KnoxLLMResponse(**response_data)
                break
            except (ValueError, ValidationError) as e:
                last_err = e
                llm_response = None  # type: ignore
        else:
            # Loop föll igenom utan break
            raise ValueError(f"LLM response parsing/validation failed after retries: {last_err}")
        
        # Log success (metadata only)
        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.info(
            "Compile successful",
            extra={
                "policy_id": request.policy.policy_id,
                "template_id": request.template_id,
                "input_fingerprint": request.input_fingerprint,
                "latency_ms": latency_ms
            }
        )
        
        return llm_response
    
    except ValueError as e:
        logger.error(f"Parse error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM response parsing failed: {str(e)}")
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Response validation failed: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    logger.info(f"Starting Fort Knox Local on port {FORTKNOX_PORT}")
    logger.info(f"TESTMODE: {TESTMODE}")
    logger.info(f"LLAMA_SERVER_URL: {LLAMA_SERVER_URL}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Lyssnar på alla interfaces (för Tailscale)
        port=FORTKNOX_PORT,
        log_level="info"
    )
