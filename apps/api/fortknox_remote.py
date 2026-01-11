"""
Fort Knox Remote Call Module - Kommunikation med Fort Knox Local på Mac.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
import requests
from pydantic import ValidationError

from schemas import KnoxInputPack, KnoxPolicy, KnoxLLMResponse

logger = logging.getLogger(__name__)

# Remote compile kan ta tid (lokal LLM). Gör detta konfigurerbart.
REQUEST_TIMEOUT = int(os.getenv("FORTKNOX_REMOTE_TIMEOUT", "180"))  # sekunder


class FortKnoxRemoteError(Exception):
    """Exception för remote call errors."""
    def __init__(self, error_code: str, reasons: list, detail: Optional[str] = None):
        self.error_code = error_code
        self.reasons = reasons
        self.detail = detail
        super().__init__(f"{error_code}: {', '.join(reasons)}")


def get_test_fixtures() -> Dict[str, Dict[str, Any]]:
    """
    Hämta fasta JSON fixtures för test mode.
    
    Returns:
        Dict med 'internal_pass' och 'external_fail' fixtures
    """
    # Internal pass fixture
    internal_pass = {
        "template_id": "weekly",
        "language": "sv",
        "title": "Testrapport - Intern",
        "executive_summary": "Detta är en testrapport för intern användning.",
        "themes": [
            {
                "name": "Tema 1",
                "bullets": ["Punkt 1", "Punkt 2"]
            }
        ],
        "timeline_high_level": ["Vecka 1: Händelse 1", "Vecka 2: Händelse 2"],
        "risks": [
            {
                "risk": "Risk 1",
                "mitigation": "Åtgärd 1"
            }
        ],
        "open_questions": ["Fråga 1", "Fråga 2"],
        "next_steps": ["Steg 1", "Steg 2"],
        "confidence": "medium"
    }
    
    # External fail fixture (provocera quote_detected)
    external_fail = {
        "template_id": "weekly",
        "language": "sv",
        "title": "Testrapport - Extern",
        "executive_summary": (
            "Detta är en testrapport för extern användning med långt citat som kommer att trigga quote detection."
        ),
        "themes": [
            {
                "name": "Tema 1",
                "bullets": [
                    (
                        "Detta är ett mycket långt citat från källan som kommer att trigga quote detection "
                        "eftersom det är för många ord i följd som matchar input texten"
                    )
                ]
            }
        ],
        "timeline_high_level": ["2025-01-15: Händelse 1", "2025-01-16: Händelse 2"],  # Exakta datum för external fail
        "risks": [
            {
                "risk": "Risk 1",
                "mitigation": "Åtgärd 1"
            }
        ],
        "open_questions": ["Fråga 1"],
        "next_steps": ["Steg 1"],
        "confidence": "low"
    }
    
    return {
        "internal_pass": internal_pass,
        "external_fail": external_fail
    }


def compile_remote(
    pack: KnoxInputPack,
    policy: KnoxPolicy,
    template_id: str,
    remote_url: Optional[str] = None
) -> KnoxLLMResponse:
    """
    Kompilera Fort Knox-rapport via remote call eller test mode.
    
    Args:
        pack: KnoxInputPack med documents, notes, sources
        policy: KnoxPolicy
        template_id: Template ID
        remote_url: Remote URL (optional, krävs om inte test mode)
    
    Returns:
        KnoxLLMResponse med validerad JSON
    
    Raises:
        FortKnoxRemoteError: Vid timeout, network error, schema validation error
    """
    # Kolla test mode
    test_mode = os.getenv("FORTKNOX_TESTMODE", "0") == "1"
    
    if test_mode:
        logger.info("FORTKNOX_TESTMODE=1: Använder fasta JSON fixtures")
        
        # Använd fixtures baserat på policy mode
        fixtures = get_test_fixtures()
        if policy.mode == "external":
            fixture_data = fixtures["external_fail"]
        else:
            fixture_data = fixtures["internal_pass"]
        
        try:
            # Validera fixture mot schema
            llm_response = KnoxLLMResponse(**fixture_data)
            logger.info(f"Test mode: Returnerar {policy.mode} fixture (validated)")
            return llm_response
        except ValidationError as e:
            logger.error(f"Test mode fixture validation failed: {e}")
            raise FortKnoxRemoteError(
                error_code="SCHEMA_VALIDATION_ERROR",
                reasons=["test_fixture_validation_failed"],
                detail=str(e)
            )
    
    # Real remote call
    if not remote_url:
        raise FortKnoxRemoteError(
            error_code="REMOTE_URL_MISSING",
            reasons=["remote_url_required"],
            detail="FORTKNOX_REMOTE_URL not set and FORTKNOX_TESTMODE=0"
        )
    
    # Bygg payload (v1: endast documents + notes, exkludera sources från payload)
    payload = {
        "policy": {
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "ruleset_hash": policy.ruleset_hash,
            "mode": policy.mode,
            "sanitize_min_level": policy.sanitize_min_level,
            "quote_limit_words": policy.quote_limit_words,
            "date_strictness": policy.date_strictness
        },
        "template_id": template_id,
        "input_fingerprint": pack.input_fingerprint,
        "documents": [
            {
                "id": doc.doc_id,
                "text": doc.masked_text
            }
            for doc in pack.documents
        ],
        "notes": [
            {
                "id": note.note_id,
                "text": note.masked_body
            }
            for note in pack.notes
        ]
        # Sources exkluderas från payload i v1
    }
    
    # Logga metadata (aldrig textinnehåll)
    logger.info(
        "Remote call: POST to Fort Knox Local",
        extra={
            "policy_id": policy.policy_id,
            "template_id": template_id,
            "input_fingerprint": pack.input_fingerprint,
            "doc_count": len(pack.documents),
            "note_count": len(pack.notes)
        }
    )
    
    try:
        # POST till remote URL
        response = requests.post(
            f"{remote_url}/compile",
            json=payload,
            timeout=REQUEST_TIMEOUT,
            headers={"Content-Type": "application/json"}
        )
        
        # Kolla status code
        if response.status_code != 200:
            logger.error(
                f"Remote call failed: status {response.status_code}",
                extra={
                    "policy_id": policy.policy_id,
                    "template_id": template_id,
                    "status_code": response.status_code
                }
            )
            raise FortKnoxRemoteError(
                error_code="REMOTE_ERROR",
                reasons=[f"http_status_{response.status_code}"],
                detail=f"Remote returned status {response.status_code}"
            )
        
        # Parse JSON response
        try:
            response_data = response.json()
        except json.JSONDecodeError as e:
            logger.error(
                "Remote call: Invalid JSON response",
                extra={
                    "policy_id": policy.policy_id,
                    "template_id": template_id
                }
            )
            raise FortKnoxRemoteError(
                error_code="REMOTE_ERROR",
                reasons=["invalid_json_response"],
                detail=str(e)
            )
        
        # Validera response mot schema (additionalProperties:false via pydantic)
        try:
            llm_response = KnoxLLMResponse(**response_data)
            logger.info(
                "Remote call: Success",
                extra={
                    "policy_id": policy.policy_id,
                    "template_id": template_id,
                    "input_fingerprint": pack.input_fingerprint
                }
            )
            return llm_response
        except ValidationError as e:
            logger.error(
                "Remote call: Schema validation failed",
                extra={
                    "policy_id": policy.policy_id,
                    "template_id": template_id
                }
            )
            raise FortKnoxRemoteError(
                error_code="SCHEMA_VALIDATION_ERROR",
                reasons=["llm_response_schema_validation_failed"],
                detail=str(e)
            )
    
    except requests.Timeout:
        logger.error(
            "Remote call: Timeout",
            extra={
                "policy_id": policy.policy_id,
                "template_id": template_id,
                "timeout": REQUEST_TIMEOUT
            }
        )
        raise FortKnoxRemoteError(
            error_code="REMOTE_ERROR",
            reasons=["timeout"],
            detail=f"Request timeout after {REQUEST_TIMEOUT}s"
        )
    
    except requests.RequestException as e:
        logger.error(
            f"Remote call: Network error: {e}",
            extra={
                "policy_id": policy.policy_id,
                "template_id": template_id
            }
        )
        raise FortKnoxRemoteError(
            error_code="REMOTE_ERROR",
            reasons=["network_error"],
            detail=str(e)
        )
