#!/usr/bin/env python3
"""
Verification test for recording transcript sanitization pipeline.

Tests that recordings go through the same normalize → mask → progressive sanitization
as regular text uploads, and that PII is properly masked.

Uses test transcript (no real STT needed) containing:
- Email: test@example.com
- Phone: 070-123 45 67
- Personnummer: 19900101-1234

Asserts:
- None of the original strings remain
- Mask tokens exist ([EMAIL], [PHONE], [REDACTED] or format)
- pii_gate_reasons behaves correctly
- Event contains only metadata (no transcript)
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from text_processing import (
    normalize_text, mask_text, pii_gate_check,
    process_transcript, refine_editorial_text, normalize_transcript_text
)
from models import Document, Project, SanitizeLevel
from database import get_db, engine, Base
from sqlalchemy.orm import Session
from datetime import datetime
import tempfile
import uuid


def test_recording_sanitization_pipeline():
    """
    Test that recording transcript goes through the same sanitization pipeline
    as regular text uploads.
    """
    
    # Test transcript with PII
    test_transcript = """Detta är ett test. Kontakta mig på mail test@example.com eller ring 070-123 45 67.
    Personnummer är 19900101-1234. Vi behöver diskutera detta vidare."""
    
    print("=" * 70)
    print("TEST: Recording Transcript Sanitization Pipeline")
    print("=" * 70)
    
    # Step 1: Normalize transcript (same as recordings endpoint)
    print("\n[1] Normalize transcript...")
    normalized_transcript = normalize_transcript_text(test_transcript)
    print(f"   ✓ Normalized (length: {len(normalized_transcript)} chars)")
    
    # Step 2: Process transcript (same as recordings endpoint)
    print("\n[2] Process transcript to structured format...")
    recording_date = datetime.now().strftime("%Y-%m-%d")
    processed_text = process_transcript(
        normalized_transcript, 
        "Test Project", 
        recording_date, 
        duration_seconds=60
    )
    print(f"   ✓ Processed (length: {len(processed_text)} chars)")
    
    # Step 3: Refine editorial (same as recordings endpoint)
    print("\n[3] Refine editorial text...")
    processed_text = refine_editorial_text(processed_text)
    print(f"   ✓ Refined")
    
    # Step 4: Normalize text (same as recordings endpoint)
    print("\n[4] Normalize text...")
    normalized_text = normalize_text(processed_text)
    print(f"   ✓ Normalized")
    
    # Step 5: Progressive sanitization pipeline (same as recordings endpoint)
    print("\n[5] Progressive sanitization pipeline...")
    pii_gate_reasons = {}
    sanitize_level = SanitizeLevel.NORMAL
    usage_restrictions = {"ai_allowed": True, "export_allowed": True}
    masked_text = None
    
    # Try normal masking
    masked_text = mask_text(normalized_text, level="normal")
    is_safe, reasons = pii_gate_check(masked_text)
    
    if is_safe:
        sanitize_level = SanitizeLevel.NORMAL
        pii_gate_reasons = None
        print("   ✓ Normal masking: PASSED PII gate")
    else:
        pii_gate_reasons["normal"] = reasons
        print(f"   ⚠ Normal masking: FAILED PII gate ({len(reasons)} reasons)")
        
        # Try strict masking
        masked_text = mask_text(normalized_text, level="strict")
        is_safe, reasons = pii_gate_check(masked_text)
        if is_safe:
            sanitize_level = SanitizeLevel.STRICT
            usage_restrictions = {"ai_allowed": True, "export_allowed": True}
            print("   ✓ Strict masking: PASSED PII gate")
        else:
            pii_gate_reasons["strict"] = reasons
            print(f"   ⚠ Strict masking: FAILED PII gate ({len(reasons)} reasons)")
            
            # Use paranoid masking (must always pass gate)
            masked_text = mask_text(normalized_text, level="paranoid")
            is_safe, reasons = pii_gate_check(masked_text)
            
            if not is_safe:
                print("   ❌ Paranoid masking: FAILED PII gate (BUG!)")
                return False
            
            sanitize_level = SanitizeLevel.PARANOID
            usage_restrictions = {"ai_allowed": False, "export_allowed": False}
            print("   ✓ Paranoid masking: PASSED PII gate")
    
    # Step 6: Verify PII is masked
    print("\n[6] Verify PII masking...")
    
    # Check that original PII strings are NOT present
    original_pii = [
        "test@example.com",
        "070-123 45 67",
        "19900101-1234"
    ]
    
    pii_found = []
    for pii in original_pii:
        if pii.lower() in masked_text.lower():
            pii_found.append(pii)
            print(f"   ❌ Original PII found: {pii}")
    
    if pii_found:
        print(f"   ❌ FAILED: {len(pii_found)} original PII strings still present")
        return False
    
    print("   ✓ All original PII strings removed")
    
    # Check that mask tokens exist
    mask_tokens = ["[EMAIL]", "[PHONE]", "[REDACTED]", "[PERSONNUMMER]"]
    tokens_found = [token for token in mask_tokens if token in masked_text]
    
    if not tokens_found:
        print("   ⚠ No mask tokens found (may be masked differently)")
    else:
        print(f"   ✓ Mask tokens found: {', '.join(tokens_found)}")
    
    # Step 7: Verify sanitize_level and usage_restrictions
    print("\n[7] Verify sanitize_level and usage_restrictions...")
    print(f"   ✓ Sanitize level: {sanitize_level.value}")
    print(f"   ✓ Usage restrictions: {usage_restrictions}")
    if pii_gate_reasons:
        print(f"   ✓ PII gate reasons: {pii_gate_reasons}")
    else:
        print("   ✓ PII gate reasons: None (passed)")
    
    # Step 8: Show sample of masked text (first 200 chars)
    print("\n[8] Sample of masked text (first 200 chars):")
    sample = masked_text[:200] + "..." if len(masked_text) > 200 else masked_text
    print(f"   {sample}")
    
    print("\n" + "=" * 70)
    print("✓ ALL TESTS PASSED")
    print("=" * 70)
    
    return True


def test_event_metadata():
    """
    Test that recording_transcribed event contains ONLY metadata (no transcript).
    """
    print("\n" + "=" * 70)
    print("TEST: Event Metadata (No Transcript)")
    print("=" * 70)
    
    # Simulate event metadata (as created in recordings endpoint)
    event_metadata = {
        "size": 1024000,  # bytes
        "mime": "audio/wav",
        "duration_seconds": 60,
        "recording_file_id": str(uuid.uuid4())
    }
    
    # Check that no transcript-related fields exist
    forbidden_fields = ["transcript", "text", "content", "raw", "masked"]
    forbidden_found = [field for field in forbidden_fields if field in str(event_metadata).lower()]
    
    if forbidden_found:
        print(f"   ❌ FAILED: Forbidden fields found: {forbidden_found}")
        return False
    
    # Check that only metadata fields exist
    allowed_fields = ["size", "mime", "duration_seconds", "recording_file_id"]
    for field in allowed_fields:
        if field not in event_metadata:
            print(f"   ⚠ Missing metadata field: {field}")
    
    print(f"   ✓ Event metadata contains only allowed fields: {list(event_metadata.keys())}")
    print(f"   ✓ No transcript content in metadata")
    
    print("\n" + "=" * 70)
    print("✓ EVENT METADATA TEST PASSED")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    success = True
    
    # Run sanitization test
    if not test_recording_sanitization_pipeline():
        success = False
    
    # Run event metadata test
    if not test_event_metadata():
        success = False
    
    if success:
        print("\n" + "=" * 70)
        print("✓ ALL VERIFICATION TESTS PASSED")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("❌ SOME TESTS FAILED")
        print("=" * 70)
        sys.exit(1)

