"""Privacy Shield Service - Defense-in-depth pipeline + policy."""
import time
import logging
from fastapi import HTTPException

from ..config import privacy_max_chars, CONTROL_MODEL_ENABLED
from .models import (
    PrivacyMaskRequest,
    PrivacyMaskResponse,
    ControlResult,
    PrivacyLeakError
)
from .regex_mask import regex_masker
from .leak_check import check_leaks

logger = logging.getLogger(__name__)


async def mask_text(request: PrivacyMaskRequest, request_id: str) -> PrivacyMaskResponse:
    """
    Mask text using defense-in-depth pipeline.
    
    Pipeline:
    1. Baseline regex mask (MUST always run)
    2. Leak check (blocking)
    3. Control check (advisory, strict mode only) - INACTIVE (CONTROL_MODEL_ENABLED=False)
    4. Return response
    
    Args:
        request: Mask request
        request_id: Request ID for tracking
        
    Returns:
        PrivacyMaskResponse
        
    Raises:
        HTTPException: If validation fails or leak detected
    """
    start_time = time.time()
    
    # Validate input length
    if len(request.text) > privacy_max_chars:
        logger.error(
            "privacy_mask_input_too_large",
            extra={
                "request_id": request_id,
                "length": len(request.text),
                "max_chars": privacy_max_chars,
                "error_type": "ValidationError"
            }
        )
        raise HTTPException(
            status_code=413,
            detail=f"Input text exceeds maximum length ({privacy_max_chars} characters)"
        )
    
    # A) Baseline mask (MUST always run) - Multi-pass for robustness
    try:
        # Pass 1: Initial masking
        masked_text, entity_counts, privacy_logs = regex_masker.mask(request.text)
        provider = "regex"
        
        # Pass 2: Re-mask on result (catches overlaps, edge cases, missed hits)
        # This is critical for edge cases with many repetitions
        masked_text_pass2, additional_counts, additional_logs = regex_masker.mask(masked_text)
        
        # Only use pass2 if it actually changed something (avoid infinite loops)
        if masked_text_pass2 != masked_text:
            masked_text = masked_text_pass2
            # Merge counts and logs
            for key in entity_counts:
                entity_counts[key] += additional_counts.get(key, 0)
            privacy_logs.extend(additional_logs)
        
        # Pass 3 (strict mode only): One more pass for maximum safety
        if request.mode == "strict":
            masked_text_pass3, additional_counts3, additional_logs3 = regex_masker.mask(masked_text)
            if masked_text_pass3 != masked_text:
                masked_text = masked_text_pass3
                for key in entity_counts:
                    entity_counts[key] += additional_counts3.get(key, 0)
                privacy_logs.extend(additional_logs3)
                
    except Exception as e:
        error_type = type(e).__name__
        logger.error(
            "privacy_mask_baseline_failed",
            extra={
                "request_id": request_id,
                "error_type": error_type
            }
        )
        raise HTTPException(
            status_code=500,
            detail="Baseline masking failed"
        )
    
    # B) Leak check (BLOCKING) - Must pass after multi-pass masking
    try:
        check_leaks(masked_text, mode=request.mode)
    except PrivacyLeakError as e:
        # After multi-pass masking, any leak is a hard failure
        logger.error(
            "privacy_mask_leak_detected",
            extra={
                "request_id": request_id,
                "error_type": "PrivacyLeakError",
                "error_code": e.error_code
            }
        )
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "pii_detected",
                    "message": "Privacy leak detected after masking",
                    "request_id": request_id
                }
            }
        )
    
    # C) Control check (ADVISORY, strict mode only) - INACTIVE
    # Control check path is preserved for minimal diff but inactive via CONTROL_MODEL_ENABLED flag
    control_result = ControlResult(ok=True, reasons=[])
    if request.mode == "strict" and CONTROL_MODEL_ENABLED:
        # NOTE: llamacpp_provider import removed - control check path inactive
        # Original code preserved below for reference (minimal diff):
        # if llamacpp_provider.is_enabled():
        #     try:
        #         masked_payload = MaskedPayload(...)
        #         control_result_dict = await llamacpp_provider.control_check(masked_payload)
        #         ...
        pass
    
    latency_ms = (time.time() - start_time) * 1000
    
    logger.info(
        "privacy_mask_complete",
        extra={
            "request_id": request_id,
            "mode": request.mode,
            "provider": provider,
            "latency_ms": round(latency_ms, 2)
        }
    )
    
    return PrivacyMaskResponse(
        maskedText=masked_text,
        summary=None,
        entities=entity_counts,
        privacyLogs=privacy_logs,
        provider=provider,
        requestId=request_id,
        control=control_result
    )

