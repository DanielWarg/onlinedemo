"""Privacy Gate - Hard enforcement for external LLM egress.

ALL external LLM calls MUST go through this gate.
No raw text can reach external APIs without passing privacy_gate.

This is the ONLY way to prepare text for external LLM providers.
"""
from fastapi import HTTPException

from .privacy_shield.service import mask_text
from .privacy_shield.models import PrivacyMaskRequest, MaskedPayload, PrivacyMaskResponse


class PrivacyGateError(Exception):
    """Error raised when privacy gate blocks request."""
    pass


async def ensure_masked_or_raise(text: str, mode: str = "strict", request_id: str = "gate") -> MaskedPayload:
    """
    Ensure text is masked and return MaskedPayload.
    
    This is the ONLY way to get text ready for external LLM calls.
    ALL external LLM providers MUST use this gate.
    
    Args:
        text: Raw text to mask
        mode: "strict" or "balanced" (default: "strict" for safety)
        request_id: Request ID for tracking
        
    Returns:
        MaskedPayload that can be safely sent to external LLM
        
    Raises:
        PrivacyGateError: If masking fails or leak detected
        HTTPException: If input validation fails
    """
    try:
        request = PrivacyMaskRequest(
            text=text,
            mode=mode,
            language="sv"
        )
        
        # Use Privacy Shield service to mask
        response: PrivacyMaskResponse = await mask_text(request, request_id)
        
        # Create MaskedPayload for external LLM
        payload = MaskedPayload(
            text=response.maskedText,
            entities=response.entities,
            privacy_logs=response.privacyLogs,
            request_id=response.requestId
        )
        
        return payload
        
    except HTTPException:
        # Re-raise HTTPException (validation errors, etc.)
        raise
    except Exception as e:
        # Wrap other exceptions as PrivacyGateError
        raise PrivacyGateError(f"Privacy gate failed: {type(e).__name__}") from e

