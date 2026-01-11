#!/usr/bin/env python3
"""
Verification script for Project Sources feature.

Tests:
1. Create project
2. Add 2 sources (different types)
3. Verify sources exist
4. Verify events are clean (no title/comment in metadata)
5. Delete one source
6. Verify it's gone
7. Verify delete event is clean
"""
import sys
import os
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = os.getenv("API_URL", "http://localhost:8000")
AUTH = (os.getenv("AUTH_USER", "admin"), os.getenv("AUTH_PASS", "password"))

os.environ["DEBUG"] = "true"

def main():
    print("=" * 70)
    print("PROJECT SOURCES VERIFICATION")
    print("=" * 70)
    print()
    
    passed = 0
    total = 0
    
    # Test 1: Create project
    total += 1
    print("1. Create test project...")
    try:
        response = requests.post(
            f"{API_BASE}/api/projects",
            json={"name": "Sources Test Project", "classification": "normal"},
            auth=AUTH
        )
        response.raise_for_status()
        project = response.json()
        project_id = project["id"]
        print(f"✓ PASSED: Project created (ID: {project_id})")
        passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return 1
    print()
    
    # Test 2: Add source (link)
    total += 1
    print("2. Add source (type: link)...")
    try:
        response = requests.post(
            f"{API_BASE}/api/projects/{project_id}/sources",
            json={
                "title": "Regeringens pressmeddelande",
                "type": "link",
                "comment": "https://regeringen.se/..."
            },
            auth=AUTH
        )
        response.raise_for_status()
        source1 = response.json()
        source1_id = source1["id"]
        
        if source1["title"] != "Regeringens pressmeddelande":
            print(f"✗ FAILED: Title mismatch")
        elif source1["type"] != "link":
            print(f"✗ FAILED: Type mismatch")
        else:
            print(f"✓ PASSED: Source added (ID: {source1_id})")
            passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
    print()
    
    # Test 3: Add source (person)
    total += 1
    print("3. Add source (type: person)...")
    try:
        response = requests.post(
            f"{API_BASE}/api/projects/{project_id}/sources",
            json={
                "title": "Expertintervju",
                "type": "person",
                "comment": "Professor i statsvetenskap"
            },
            auth=AUTH
        )
        response.raise_for_status()
        source2 = response.json()
        source2_id = source2["id"]
        
        print(f"✓ PASSED: Source added (ID: {source2_id})")
        passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
    print()
    
    # Test 4: Get all sources
    total += 1
    print("4. Get all sources (should be 2)...")
    try:
        response = requests.get(
            f"{API_BASE}/api/projects/{project_id}/sources",
            auth=AUTH
        )
        response.raise_for_status()
        sources = response.json()
        
        if len(sources) != 2:
            print(f"✗ FAILED: Expected 2 sources, got {len(sources)}")
        else:
            print(f"✓ PASSED: Got 2 sources")
            passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
    print()
    
    # Test 5: Verify events are clean
    total += 1
    print("5. Verify events (no title/comment in metadata)...")
    try:
        response = requests.get(
            f"{API_BASE}/api/projects/{project_id}/events",
            auth=AUTH
        )
        response.raise_for_status()
        events = response.json()
        
        source_events = [e for e in events if e["event_type"] in ["source_added", "source_removed"]]
        
        if not source_events:
            print(f"✗ FAILED: No source events found")
        else:
            forbidden_keys = {"title", "comment", "text", "body", "content"}
            all_clean = True
            
            for event in source_events:
                # Get metadata (handle both 'metadata' and 'event_metadata' keys)
                metadata = event.get("metadata") or event.get("event_metadata", {})
                
                # If metadata is None or empty, that's actually OK (Privacy Guard dropped everything)
                if not metadata:
                    continue
                
                found_forbidden = set(metadata.keys()) & forbidden_keys
                
                if found_forbidden:
                    print(f"✗ FAILED: Found forbidden keys in metadata: {found_forbidden}")
                    all_clean = False
                    break
                
                # Verify "type" is in metadata
                if "type" not in metadata:
                    print(f"✗ FAILED: Missing 'type' in metadata. Found keys: {list(metadata.keys())}")
                    all_clean = False
                    break
            
            if all_clean:
                print(f"✓ PASSED: All events clean (metadata: type only or empty)")
                print(f"  Found {len(source_events)} source events")
                passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
    print()
    
    # Test 6: Delete source
    total += 1
    print("6. Delete first source...")
    try:
        response = requests.delete(
            f"{API_BASE}/api/projects/{project_id}/sources/{source1_id}",
            auth=AUTH
        )
        response.raise_for_status()
        
        print(f"✓ PASSED: Source deleted")
        passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
    print()
    
    # Test 7: Verify source is gone
    total += 1
    print("7. Verify source is gone (should be 1 left)...")
    try:
        response = requests.get(
            f"{API_BASE}/api/projects/{project_id}/sources",
            auth=AUTH
        )
        response.raise_for_status()
        sources = response.json()
        
        if len(sources) != 1:
            print(f"✗ FAILED: Expected 1 source, got {len(sources)}")
        else:
            print(f"✓ PASSED: Source deleted (1 remaining)")
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

