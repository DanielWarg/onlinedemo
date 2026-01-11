#!/usr/bin/env python3
"""
Verification script for sanitization pipeline.
Tests that safe documents pass through normal/strict (not paranoid).
"""
import sys
import os
import requests
import json
from pathlib import Path

# Add parent directory to path to import text_processing
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = os.getenv("API_URL", "http://localhost:8000")
AUTH_USER = os.getenv("AUTH_USER", "admin")
AUTH_PASS = os.getenv("AUTH_PASS", "password")

def main():
    print("=" * 70)
    print("SANITIZATION VERIFICATION TEST")
    print("=" * 70)
    
    # Setup auth
    auth = (AUTH_USER, AUTH_PASS)
    
    # Step 1: Create a test project
    print("\n1. Creating test project...")
    project_data = {
        "name": "Sanitization Test Project",
        "description": "Test project for sanitization verification",
        "classification": "normal"
    }
    response = requests.post(
        f"{API_BASE}/api/projects",
        json=project_data,
        auth=auth
    )
    if response.status_code != 201:
        print(f"✗ Failed to create project: {response.status_code}")
        print(response.text)
        return 1
    
    project = response.json()
    project_id = project["id"]
    print(f"✓ Project created (ID: {project_id})")
    
    # Step 2: Upload safe_document.txt
    print("\n2. Uploading safe_document.txt...")
    fixture_path = Path(__file__).parent / "safe_document.txt"
    if not fixture_path.exists():
        print(f"✗ Test fixture not found: {fixture_path}")
        return 1
    
    with open(fixture_path, 'rb') as f:
        files = {'file': ('safe_document.txt', f, 'text/plain')}
        response = requests.post(
            f"{API_BASE}/api/projects/{project_id}/documents",
            files=files,
            auth=auth
        )
    
    if response.status_code != 201:
        print(f"✗ Failed to upload document: {response.status_code}")
        print(response.text)
        return 1
    
    document = response.json()
    document_id = document["id"]
    print(f"✓ Document uploaded (ID: {document_id})")
    
    # Step 3: Verify sanitize_level
    print("\n3. Verifying sanitize_level...")
    sanitize_level = document.get("sanitize_level")
    print(f"   sanitize_level: {sanitize_level}")
    
    if sanitize_level == "paranoid":
        print("✗ FAILED: Document escalated to paranoid (should be normal or strict)")
        print(f"   pii_gate_reasons: {document.get('pii_gate_reasons')}")
        return 1
    elif sanitize_level not in ["normal", "strict"]:
        print(f"✗ FAILED: Unexpected sanitize_level: {sanitize_level}")
        return 1
    else:
        print(f"✓ sanitize_level is {sanitize_level} (not paranoid)")
    
    # Step 4: Verify usage_restrictions
    print("\n4. Verifying usage_restrictions...")
    usage_restrictions = document.get("usage_restrictions", {})
    ai_allowed = usage_restrictions.get("ai_allowed", False)
    export_allowed = usage_restrictions.get("export_allowed", False)
    
    print(f"   ai_allowed: {ai_allowed}")
    print(f"   export_allowed: {export_allowed}")
    
    if not ai_allowed:
        print("✗ FAILED: ai_allowed is False (should be True)")
        return 1
    if not export_allowed:
        print("✗ FAILED: export_allowed is False (should be True)")
        return 1
    
    print("✓ usage_restrictions allow AI and export")
    
    # Step 5: Verify masked content
    print("\n5. Verifying masked content...")
    response = requests.get(
        f"{API_BASE}/api/documents/{document_id}",
        auth=auth
    )
    if response.status_code != 200:
        print(f"✗ Failed to fetch document: {response.status_code}")
        return 1
    
    full_document = response.json()
    masked_text = full_document.get("masked_text", "")
    
    # Check that email is masked
    if "[EMAIL]" not in masked_text:
        print("✗ FAILED: Email not masked as [EMAIL]")
        print(f"   Masked text preview: {masked_text[:200]}")
        return 1
    print("✓ Email masked: [EMAIL]")
    
    # Check that phone is masked
    if "[PHONE]" not in masked_text:
        print("✗ FAILED: Phone not masked as [PHONE]")
        print(f"   Masked text preview: {masked_text[:200]}")
        return 1
    print("✓ Phone masked: [PHONE]")
    
    # Check that date is preserved
    if "2025-11-20" not in masked_text:
        print("✗ FAILED: Date not preserved")
        return 1
    print("✓ Date preserved: 2025-11-20")
    
    # Check that amount is preserved (may be masked as [NUM] in strict, that's OK)
    if "24 698" not in masked_text and "[NUM]" not in masked_text:
        print("✗ FAILED: Amount not preserved or masked")
        return 1
    if "24 698" in masked_text:
        print("✓ Amount preserved: 24 698 kr")
    else:
        print("✓ Amount masked as [NUM] (strict level)")
    
    # Check that case number is preserved
    if "Ä 16923-25" not in masked_text and "16923-25" not in masked_text:
        print("✗ FAILED: Case number not preserved")
        print(f"   Masked text preview: {masked_text}")
        return 1
    print("✓ Case number preserved: Ä 16923-25")
    
    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"✓ Document uploaded successfully")
    print(f"✓ sanitize_level: {sanitize_level} (not paranoid)")
    print(f"✓ usage_restrictions: ai_allowed={ai_allowed}, export_allowed={export_allowed}")
    print(f"✓ Email and phone masked correctly")
    print(f"✓ Date, amount, and case number preserved")
    print("\n✓ All verification tests passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())

