#!/usr/bin/env python3
"""Verifiera att Security Core kan importeras och fungerar korrekt.

Kontrollerar:
- Modulen kan importeras utan fel
- Masking fungerar på testtext
- Inga endpoints använder Security Core
"""
import os
import sys
import asyncio
from pathlib import Path

# Ensure we can import from apps/api
api_dir = Path(__file__).parent.parent
sys.path.insert(0, str(api_dir))

# Test imports
print("[1] Testing imports...")
try:
    from security_core.privacy_shield.service import mask_text
    from security_core.privacy_shield.models import PrivacyMaskRequest, MaskedPayload
    from security_core.privacy_gate import ensure_masked_or_raise, PrivacyGateError
    from security_core.privacy_guard import sanitize_for_logging, assert_no_content
    print("   ✓ All imports successful")
except ImportError as e:
    print(f"   ❌ Import failed: {e}")
    sys.exit(1)

# Test masking
print("\n[2] Testing Privacy Shield masking...")
test_text = "Kontakta mig på test@example.com eller ring 070-123 45 67. Personnummer: 19900101-1234."

async def test_masking():
    try:
        request = PrivacyMaskRequest(
            text=test_text,
            mode="balanced",
            language="sv"
        )
        response = await mask_text(request, request_id="test-123")
        
        # Verify PII is masked
        assert "[EMAIL]" in response.maskedText, "Email not masked"
        assert "[PHONE]" in response.maskedText, "Phone not masked"
        assert "[PNR]" in response.maskedText, "Personnummer not masked"
        assert "test@example.com" not in response.maskedText, "Original email found"
        assert "070-123 45 67" not in response.maskedText, "Original phone found"
        assert "19900101-1234" not in response.maskedText, "Original personnummer found"
        
        print("   ✓ Masking works correctly")
        print(f"   ✓ Masked text: {response.maskedText[:100]}...")
        return True
    except Exception as e:
        print(f"   ❌ Masking failed: {e}")
        import traceback
        traceback.print_exc()
        return False

result = asyncio.run(test_masking())
if not result:
    sys.exit(1)

# Test Privacy Gate
print("\n[3] Testing Privacy Gate...")
async def test_privacy_gate():
    try:
        masked_payload = await ensure_masked_or_raise(
            test_text,
            mode="strict",
            request_id="test-gate"
        )
        
        assert isinstance(masked_payload, MaskedPayload), "Not a MaskedPayload"
        assert "[EMAIL]" in masked_payload.text, "Email not masked in payload"
        assert "test@example.com" not in masked_payload.text, "Original email in payload"
        
        print("   ✓ Privacy Gate works correctly")
        print(f"   ✓ MaskedPayload created: {len(masked_payload.text)} chars")
        return True
    except Exception as e:
        print(f"   ❌ Privacy Gate failed: {e}")
        import traceback
        traceback.print_exc()
        return False

result = asyncio.run(test_privacy_gate())
if not result:
    sys.exit(1)

# Test Privacy Guard
print("\n[4] Testing Privacy Guard...")
try:
    # Test sanitize_for_logging
    test_data = {
        "request_id": "123",
        "status": "ok",
        "text": "This should be removed",  # Forbidden key
        "transcript": "Also forbidden",     # Forbidden key
        "count": 5,  # Allowed
        "metadata": {
            "size": 1024,
            "content": "Also forbidden"  # Forbidden key
        }
    }
    
    sanitized = sanitize_for_logging(test_data, context="test")
    assert "text" not in sanitized, "Forbidden key 'text' not removed"
    assert "transcript" not in sanitized, "Forbidden key 'transcript' not removed"
    assert "content" not in sanitized.get("metadata", {}), "Forbidden key 'content' in nested dict not removed"
    assert sanitized["request_id"] == "123", "Allowed key removed"
    assert sanitized["count"] == 5, "Allowed key removed"
    
    print("   ✓ sanitize_for_logging works correctly")
    
    # Test assert_no_content (should raise)
    try:
        assert_no_content({"text": "forbidden"}, context="test")
        print("   ❌ assert_no_content did not raise AssertionError")
        sys.exit(1)
    except AssertionError:
        print("   ✓ assert_no_content correctly raises AssertionError")
    
    # Test assert_no_content (should pass)
    assert_no_content({"request_id": "123", "count": 5}, context="test")
    print("   ✓ assert_no_content correctly passes for safe data")
    
except Exception as e:
    print(f"   ❌ Privacy Guard failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verify no endpoints use Security Core
print("\n[5] Verifying no endpoints import Security Core...")
main_py = api_dir / "main.py"
text_processing_py = api_dir / "text_processing.py"

imports_found = []
for file_path in [main_py, text_processing_py]:
    if file_path.exists():
        content = file_path.read_text(encoding='utf-8')
        if "security_core" in content.lower() or "from security_core" in content:
            imports_found.append(str(file_path))

if imports_found:
    print(f"   ❌ Security Core imports found in: {imports_found}")
    sys.exit(1)
else:
    print("   ✓ No Security Core imports in endpoints (correct)")

print("\n" + "="*60)
print("✅ ALL TESTS PASSED")
print("="*60)
print("\nSecurity Core verifierat:")
print("  - Modulen kan importeras utan fel")
print("  - Masking fungerar korrekt")
print("  - Privacy Gate fungerar korrekt")
print("  - Privacy Guard fungerar korrekt")
print("  - Inga endpoints använder Security Core (förväntat)")
print("\nModulen är dormant och klar för framtida extern AI-integration.")

