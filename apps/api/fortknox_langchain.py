import json
import os
import time
from typing import Any, Dict, Tuple

from pydantic import ValidationError

from schemas import KnoxInputPack, KnoxPolicy, KnoxLLMResponse


class FortKnoxLangChainConfigError(RuntimeError):
    """Raised when LangChain pipeline is not configured/enabled."""


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _require_langchain_enabled():
    if os.getenv("FORTKNOX_PIPELINE", "default").strip().lower() != "langchain":
        raise FortKnoxLangChainConfigError("LangChain pipeline disabled (set FORTKNOX_PIPELINE=langchain)")


def build_langchain_prompt(pack: KnoxInputPack, policy: KnoxPolicy, template_id: str) -> str:
    """
    Build a deterministic prompt for LangChain path.
    IMPORTANT: pack already contains masked text (no raw content should be logged).
    """
    # Keep it deterministic: only use stable fields and canonical_json-like formatting.
    # Pack includes masked texts; still: do not log it.
    policy_id = getattr(policy, "policy_id", "unknown")
    policy_version = getattr(policy, "policy_version", "unknown")

    # Minimal JSON schema hint: Pydantic model fields.
    schema_hint = {
        "template_id": template_id,
        "language": "sv",
        "title": "string",
        "executive_summary": "string",
        "themes": [{"name": "string", "bullets": ["string"]}],
        "timeline_high_level": ["string"],
        "risks": [{"risk": "string", "mitigation": "string"}],
        "open_questions": ["string"],
        "next_steps": ["string"],
        "confidence": "low|medium|high",
    }

    # The actual content is passed in full to the LLM via a JSON blob.
    # This mirrors existing Fort Knox remote interface: structured input pack.
    payload = {
        "policy": {"id": policy_id, "version": policy_version, "ruleset": getattr(policy, "ruleset_hash", None)},
        "input_fingerprint": pack.input_fingerprint,
        "manifest": pack.input_manifest,  # metadata-only
        "documents": [
            {"id": d.doc_id, "sanitize_level": d.sanitize_level, "text": d.masked_text}
            for d in pack.documents
        ],
        "notes": [
            {"id": n.note_id, "sanitize_level": n.sanitize_level, "text": n.masked_body}
            for n in pack.notes
        ],
    }

    prompt = (
        "Du är Fort Knox. Du ska skapa en säker, journalistiskt användbar sammanställning på svenska.\n"
        "KRAV (måste följas):\n"
        "- Svara ENDAST med giltig JSON (ingen markdown, inga kodblock).\n"
        "- Inga personuppgifter. Inga identifierande detaljer. Inga exakta citat längre än några få ord.\n"
        "- Använd inte rå frasering från underlaget; parafrasera.\n"
        "- Följ exakt schema (additionalProperties=false).\n"
        f"- template_id ska vara '{template_id}'. language ska vara 'sv'.\n"
        "\n"
        "SCHEMA-EXEMPEL (typer):\n"
        f"{json.dumps(schema_hint, ensure_ascii=False)}\n"
        "\n"
        "UNDERLAG (JSON):\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
    )
    return prompt


def run_langchain_llm(prompt: str) -> Tuple[Dict[str, Any], int]:
    """
    Call an LLM via LangChain ChatOpenAI.
    Supports:
    - local OpenAI-compatible endpoint (default, requires FORTKNOX_LC_BASE_URL)
    - OpenAI API (requires OPENAI_API_KEY and FORTKNOX_LC_PROVIDER=openai)
    Returns (parsed_json, latency_ms).
    Fail-closed: if misconfigured, raises FortKnoxLangChainConfigError.
    """
    _require_langchain_enabled()

    provider = os.getenv("FORTKNOX_LC_PROVIDER", "local").strip().lower()
    base_url = os.getenv("FORTKNOX_LC_BASE_URL", "").strip()
    model = os.getenv("FORTKNOX_LC_MODEL", "").strip() or ("gpt-4o-mini" if provider == "openai" else "local-model")

    # Optional: allow turning on verbose retries later; keep default minimal.
    temperature = float(os.getenv("FORTKNOX_LC_TEMPERATURE", "0.2"))
    max_retries = int(os.getenv("FORTKNOX_LC_MAX_RETRIES", "2"))

    # Import inside function so API can run even if deps missing in some envs.
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise FortKnoxLangChainConfigError("Missing OPENAI_API_KEY (required for FORTKNOX_LC_PROVIDER=openai)")
        llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_retries=max_retries,
        )
    else:
        # Default: local OpenAI-compatible endpoint
        if not base_url:
            raise FortKnoxLangChainConfigError("Missing FORTKNOX_LC_BASE_URL (required for local provider)")
        llm = ChatOpenAI(
            base_url=base_url,
            api_key=os.getenv("FORTKNOX_LC_API_KEY", "local"),
            model=model,
            temperature=temperature,
            max_retries=max_retries,
        )

    started = time.time()
    resp = llm.invoke([HumanMessage(content=prompt)])
    latency_ms = int((time.time() - started) * 1000)

    text = (getattr(resp, "content", None) or "").strip()
    # Fail-closed: must be JSON
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM returned non-object JSON")
    return data, latency_ms


def parse_and_validate(response_dict: Dict[str, Any]) -> KnoxLLMResponse:
    """Validate response against strict schema."""
    return KnoxLLMResponse(**response_dict)


def compile_with_langchain(pack: KnoxInputPack, policy: KnoxPolicy, template_id: str) -> Tuple[KnoxLLMResponse, int]:
    """
    Full LangChain compile: prompt -> LLM -> strict validation.
    Returns (KnoxLLMResponse, latency_ms).
    """
    prompt = build_langchain_prompt(pack, policy, template_id)
    response_dict, latency_ms = run_langchain_llm(prompt)
    try:
        llm_response = parse_and_validate(response_dict)
    except ValidationError as e:
        # Fail-closed: surface as exception to caller; caller decides HTTP mapping.
        raise ValueError("LLM response schema validation failed") from e
    return llm_response, latency_ms

