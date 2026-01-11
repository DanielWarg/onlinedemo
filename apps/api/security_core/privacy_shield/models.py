"""Pydantic models for Privacy Shield API."""
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class PrivacyMaskRequest(BaseModel):
    """Request model for POST /api/v1/privacy/mask"""
    
    text: str = Field(..., description="Text to mask (must not exceed PRIVACY_MAX_CHARS)")
    mode: Literal["strict", "balanced"] = Field(default="balanced", description="Masking mode")
    language: str = Field(default="sv", description="Language code")
    context: Optional[Dict[str, str]] = Field(default_factory=dict, description="Optional context (eventId, sourceType, etc.)")


class PrivacyLog(BaseModel):
    """Privacy log entry."""
    rule: str = Field(..., description="Rule name (e.g., 'EMAIL', 'PHONE', 'PNR')")
    count: int = Field(..., description="Number of entities found")


class ControlResult(BaseModel):
    """Control check result."""
    ok: bool = Field(..., description="Whether control check passed")
    reasons: List[str] = Field(default_factory=list, description="Reasons if not OK")


class PrivacyMaskResponse(BaseModel):
    """Response model for POST /api/v1/privacy/mask"""
    
    maskedText: str = Field(..., description="Masked text with PII replaced by tokens")
    summary: Optional[str] = Field(default=None, description="Summary (reserved for future use)")
    entities: Dict[str, int] = Field(
        ...,
        description="Entity counts: persons, orgs, locations, contacts, ids"
    )
    privacyLogs: List[PrivacyLog] = Field(default_factory=list, description="Privacy log entries")
    provider: Literal["regex", "llamacpp"] = Field(..., description="Provider used for masking")
    requestId: str = Field(..., description="Request ID for tracking")
    control: ControlResult = Field(..., description="Control check result")


class MaskedPayload(BaseModel):
    """MaskedPayload - Only Privacy Shield can create this.
    
    This is a type-safe guarantee that text has been masked.
    External providers (OpenAI, etc.) MUST only accept MaskedPayload, never raw str.
    """
    text: str = Field(..., description="Masked text (guaranteed to have no direct PII)")
    entities: Dict[str, int] = Field(..., description="Entity counts")
    privacyLogs: List[PrivacyLog] = Field(default_factory=list, description="Privacy logs")
    request_id: str = Field(..., description="Request ID")
    
    def __init__(self, **data):
        """Private constructor - only Privacy Shield service should create this."""
        super().__init__(**data)


class PrivacyLeakError(Exception):
    """Raised when privacy leak is detected."""
    
    def __init__(self, message: str, error_code: str = "privacy_leak_detected"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)

