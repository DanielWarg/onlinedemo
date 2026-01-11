"""Privacy Guard - Paranoid content protection.

Forbids logging of any content, enforces strict limits on metadata.
DEV: raises AssertionError
PROD: drops fields + logs safe warning event.
"""
import hashlib
import logging
from typing import Any, Dict, List, Set

from .config import source_safety_mode, debug

logger = logging.getLogger(__name__)


# Forbidden keys that must NEVER appear in logs/audit (content protection)
_FORBIDDEN_CONTENT_KEYS = frozenset({
    "body",
    "headers",
    "authorization",
    "cookie",
    "text",
    "content",
    "transcript",
    "note_body",
    "file_content",
    "payload",
    "query_params",
    "query",
    "segment_text",
    "transcript_text",
    "file_data",
    "raw_content",
    "original_text",
})

# Forbidden keys for source protection (journalistic source safety)
# These can identify sources and must NEVER appear in logs/audit
_FORBIDDEN_SOURCE_KEYS = frozenset({
    "ip",
    "ip_address",
    "client_ip",
    "remote_addr",
    "x-forwarded-for",
    "x-real-ip",
    "user_agent",
    "user-agent",
    "referer",
    "referrer",
    "origin",
    "url",
    "uri",
    "filename",
    "filepath",
    "file_path",
    "original_filename",
    "querystring",
    "query_string",
    "cookies",
    "cookie",
    "headers",
    "host",
    "hostname",
})

# Maximum string length in audit/log metadata (counts/ids only)
_MAX_METADATA_STRING_LENGTH = 512


def sanitize_for_logging(data: Dict[str, Any], context: str = "log") -> Dict[str, Any]:
    """Sanitize data for logging/audit (remove content and source identifiers, truncate strings).
    
    Args:
        data: Data dictionary to sanitize
        context: Context ("log" or "audit")
        
    Returns:
        Sanitized dictionary (content and source identifiers removed, strings truncated)
        
    Raises:
        AssertionError: In DEV mode if forbidden keys found
    """
    sanitized: Dict[str, Any] = {}
    violations: List[str] = []
    
    # Combine forbidden keys (content + source protection)
    forbidden_keys = _FORBIDDEN_CONTENT_KEYS
    if source_safety_mode:
        forbidden_keys = forbidden_keys | _FORBIDDEN_SOURCE_KEYS
    
    for key, value in data.items():
        key_lower = key.lower()
        
        # Check for forbidden keys (content or source identifiers)
        if key_lower in forbidden_keys:
            violations.append(key)
            if debug:
                violation_type = "source identifier" if key_lower in _FORBIDDEN_SOURCE_KEYS else "content"
                raise AssertionError(
                    f"Privacy violation in {context}: forbidden {violation_type} key '{key}' found. "
                    f"Source identifiers and content are never allowed in logs/audit when SOURCE_SAFETY_MODE is enabled."
                )
            # PROD: drop the field silently
            continue
        
        # Truncate long strings
        if isinstance(value, str) and len(value) > _MAX_METADATA_STRING_LENGTH:
            if debug:
                raise AssertionError(
                    f"Privacy violation in {context}: string too long for key '{key}' "
                    f"({len(value)} chars > {_MAX_METADATA_STRING_LENGTH}). "
                    f"Metadata should only contain counts/ids, not content."
                )
            # PROD: truncate
            sanitized[key] = value[:_MAX_METADATA_STRING_LENGTH] + "...[truncated]"
        elif isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = sanitize_for_logging(value, context)
        elif isinstance(value, list):
            # For lists, sanitize each item if dict, otherwise keep as-is (if short)
            sanitized[key] = [
                sanitize_for_logging(item, context) if isinstance(item, dict) else item
                for item in value[:10]  # Limit list size
            ]
        else:
            sanitized[key] = value
    
    # Log warning in PROD if violations found (but don't fail)
    if violations and not debug:
        logger.warning(
            "privacy_guard_violation",
            extra={
                "context": context,
                "violations_count": len(violations),
                "violations": violations[:5],  # Only first 5
            },
        )
    
    return sanitized


def assert_no_content(data: Dict[str, Any], context: str = "audit") -> None:
    """Assert that data contains no content or source identifier fields (strict check).
    
    Args:
        data: Data dictionary to check
        context: Context for error message
        
    Raises:
        AssertionError: If forbidden content or source keys found
    """
    violations: Set[str] = set()
    
    # Combine forbidden keys
    forbidden_keys = _FORBIDDEN_CONTENT_KEYS
    if source_safety_mode:
        forbidden_keys = forbidden_keys | _FORBIDDEN_SOURCE_KEYS
    
    def _check_dict(d: Dict[str, Any], path: str = "") -> None:
        for key, value in d.items():
            key_lower = key.lower()
            current_path = f"{path}.{key}" if path else key
            
            if key_lower in forbidden_keys:
                violations.add(current_path)
            
            if isinstance(value, dict):
                _check_dict(value, current_path)
            elif isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, dict):
                        _check_dict(item, f"{current_path}[{idx}]")
    
    _check_dict(data)
    
    if violations:
        violation_type = "content or source identifiers" if source_safety_mode else "content"
        raise AssertionError(
            f"Privacy violation in {context}: forbidden {violation_type} keys found: {violations}. "
            f"Content and source identifiers must never appear in logs/audit."
        )


def compute_integrity_hash(content: str) -> str:
    """Compute SHA256 hash for content integrity verification.
    
    Args:
        content: Content string to hash
        
    Returns:
        SHA256 hex digest
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def verify_integrity(content: str, expected_hash: str) -> bool:
    """Verify content integrity against expected hash.
    
    Args:
        content: Content string to verify
        expected_hash: Expected SHA256 hash
        
    Returns:
        True if hash matches, False otherwise
    """
    actual_hash = compute_integrity_hash(content)
    return actual_hash == expected_hash

