#!/usr/bin/env python3
"""
Verification script for Event "No Content" Policy.

Tests that events never contain content or source identifiers.
Runs in DEV mode (DEBUG=true) to prove fail-closed behavior.
"""
import sys
import os
import requests
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = os.getenv("API_URL", "http://localhost:8000")
AUTH_USER = os.getenv("AUTH_USER", "admin")
AUTH_PASS = os.getenv("AUTH_PASS", "password")

# Set DEBUG=true for DEV mode (fail-closed with AssertionError)
os.environ["DEBUG"] = "true"

def main():
    print("=" * 70)
    print("EVENT NO CONTENT POLICY VERIFICATION")
    print("=" * 70)
    print(f"Running in DEV mode (DEBUG=true) to prove fail-closed behavior")
    print()
    
    auth = (AUTH_USER, AUTH_PASS)
    passed = 0
    failed = 0
    
    # Setup: Create a test project
    print("1. Creating test project...")
    project_data = {
        "name": "Event Policy Test Project",
        "description": "Test project for event policy verification",
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
    print()
    
    # Test 1: Try to create event with forbidden content key
    print("2. Test 1: Forbidden content key (should raise AssertionError in DEV)...")
    try:
        # This should fail because we're trying to pass content directly
        # We'll test by creating an event via the API endpoint
        # But first, let's test the helper function directly
        from security_core.privacy_guard import sanitize_for_logging, assert_no_content
        
        test_metadata = {"text": "This is forbidden content"}
        try:
            sanitized = sanitize_for_logging(test_metadata, context="audit")
            assert_no_content(sanitized, context="audit")
            print("✗ FAILED: Should have raised AssertionError for 'text' key")
            failed += 1
        except AssertionError as e:
            print(f"✓ PASSED: AssertionError raised as expected")
            print(f"  Error message: {str(e)[:100]}...")
            passed += 1
    except Exception as e:
        print(f"✗ FAILED: Unexpected error: {type(e).__name__}: {e}")
        failed += 1
    print()
    
    # Test 2: Try to create event with forbidden source identifier key
    print("3. Test 2: Forbidden source identifier key (should raise AssertionError in DEV)...")
    try:
        from security_core.privacy_guard import sanitize_for_logging, assert_no_content
        
        test_metadata = {"filename": "secret.pdf"}
        try:
            sanitized = sanitize_for_logging(test_metadata, context="audit")
            assert_no_content(sanitized, context="audit")
            print("✗ FAILED: Should have raised AssertionError for 'filename' key")
            failed += 1
        except AssertionError as e:
            print(f"✓ PASSED: AssertionError raised as expected")
            print(f"  Error message: {str(e)[:100]}...")
            passed += 1
    except Exception as e:
        print(f"✗ FAILED: Unexpected error: {type(e).__name__}: {e}")
        failed += 1
    print()
    
    # Test 3: Create event with harmless metadata (should pass)
    print("4. Test 3: Harmless metadata (should pass)...")
    try:
        event_data = {
            "event_type": "test_event",
            "actor": "test_user",
            "metadata": {"project_id": project_id, "count": 1}
        }
        response = requests.post(
            f"{API_BASE}/api/projects/{project_id}/events",
            json=event_data,
            auth=auth
        )
        if response.status_code == 201:
            print("✓ PASSED: Event created with harmless metadata")
            passed += 1
        else:
            print(f"✗ FAILED: Unexpected status code: {response.status_code}")
            print(response.text)
            failed += 1
    except Exception as e:
        print(f"✗ FAILED: Unexpected error: {type(e).__name__}: {e}")
        failed += 1
    print()
    
    # Test 4: Verify that existing events don't contain forbidden keys
    print("5. Test 4: Verify existing events don't contain forbidden keys...")
    try:
        response = requests.get(
            f"{API_BASE}/api/projects/{project_id}/events",
            auth=auth
        )
        if response.status_code == 200:
            events = response.json()
            forbidden_keys = ["text", "body", "content", "transcript", "filename", "file_path", "ip", "user_agent"]
            violations = []
            
            for event in events:
                metadata = event.get("metadata", {})
                if metadata:
                    for key in forbidden_keys:
                        if key in metadata:
                            violations.append(f"Event {event['id']}: found forbidden key '{key}'")
            
            if violations:
                print(f"✗ FAILED: Found {len(violations)} violations:")
                for v in violations[:5]:  # Show first 5
                    print(f"  - {v}")
                failed += 1
            else:
                print(f"✓ PASSED: No forbidden keys found in {len(events)} events")
                passed += 1
        else:
            print(f"✗ FAILED: Could not fetch events: {response.status_code}")
            failed += 1
    except Exception as e:
        print(f"✗ FAILED: Unexpected error: {type(e).__name__}: {e}")
        failed += 1
    print()
    
    # Summary
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()
    
    if failed == 0:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())

