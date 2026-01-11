#!/usr/bin/env python3
"""
Verification script for Project Status feature.

Tests:
1. Default status == research
2. PATCH all valid status values
3. PATCH invalid status -> 422
4. Event metadata is clean (no forbidden keys)
"""
import sys
import os
import requests
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = os.getenv("API_URL", "http://localhost:8000")
AUTH = (os.getenv("AUTH_USER", "admin"), os.getenv("AUTH_PASS", "password"))

# Set DEBUG=true for fail-closed proof
os.environ["DEBUG"] = "true"

def main():
    print("=" * 70)
    print("PROJECT STATUS VERIFICATION")
    print("=" * 70)
    print()
    
    passed = 0
    total = 0
    
    # Test 1: Create project -> status == research
    total += 1
    print("1. Test default status (should be 'research')...")
    try:
        response = requests.post(
            f"{API_BASE}/api/projects",
            json={"name": "Status Test Project", "classification": "normal"},
            auth=AUTH
        )
        response.raise_for_status()
        project = response.json()
        project_id = project["id"]
        
        if project["status"] != "research":
            print(f"✗ FAILED: Expected status 'research', got '{project['status']}'")
        else:
            print(f"✓ PASSED: Default status is 'research'")
            passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return 1
    print()
    
    # Test 2: PATCH all valid statuses
    valid_statuses = ["research", "processing", "fact_check", "ready", "archived"]
    for new_status in valid_statuses[1:]:  # Skip research (already set)
        total += 1
        print(f"2.{valid_statuses.index(new_status)}. Test PATCH status -> '{new_status}'...")
        try:
            response = requests.patch(
                f"{API_BASE}/api/projects/{project_id}/status",
                json={"status": new_status},
                auth=AUTH
            )
            response.raise_for_status()
            updated_project = response.json()
            
            if updated_project["status"] != new_status:
                print(f"✗ FAILED: Expected '{new_status}', got '{updated_project['status']}'")
            else:
                print(f"✓ PASSED: Status updated to '{new_status}'")
                passed += 1
        except Exception as e:
            print(f"✗ FAILED: {e}")
        print()
    
    # Test 3: PATCH invalid status -> 422
    total += 1
    print("3. Test PATCH invalid status (should return 422)...")
    try:
        response = requests.patch(
            f"{API_BASE}/api/projects/{project_id}/status",
            json={"status": "invalid_status"},
            auth=AUTH
        )
        
        if response.status_code == 422:
            print(f"✓ PASSED: Invalid status rejected with 422")
            passed += 1
        else:
            print(f"✗ FAILED: Expected 422, got {response.status_code}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
    print()
    
    # Test 4: Verify event metadata is clean
    total += 1
    print("4. Test event metadata (no forbidden keys)...")
    try:
        response = requests.get(
            f"{API_BASE}/api/projects/{project_id}/events",
            auth=AUTH
        )
        response.raise_for_status()
        events = response.json()
        
        # Find status change events
        status_events = [e for e in events if e["event_type"] == "project_status_changed"]
        
        if not status_events:
            print(f"✗ FAILED: No status change events found")
        else:
            forbidden_keys = {"text", "body", "content", "transcript", "filename", "path"}
            all_clean = True
            
            for event in status_events:
                metadata = event.get("event_metadata", {})
                found_forbidden = set(metadata.keys()) & forbidden_keys
                
                if found_forbidden:
                    print(f"✗ FAILED: Found forbidden keys in metadata: {found_forbidden}")
                    all_clean = False
                    break
                
                # Verify expected keys
                if "from" not in metadata or "to" not in metadata:
                    print(f"✗ FAILED: Missing 'from' or 'to' in metadata")
                    all_clean = False
                    break
            
            if all_clean:
                print(f"✓ PASSED: All events clean (metadata only, no forbidden keys)")
                print(f"  Found {len(status_events)} status change events")
                passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
    print()
    
    # Summary
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"Passed: {passed}/{total}")
    print()
    
    if passed == total:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
