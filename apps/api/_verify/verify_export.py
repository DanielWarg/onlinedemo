#!/usr/bin/env python3
"""
Verify export functionality:
- Markdown export works
- Toggles work correctly
- Notes NOT included by default (privacy-critical)
- Events are metadata-only (no content leakage)
"""
import sys
import requests
from pathlib import Path

API_BASE = "http://localhost:8000"
AUTH = ("admin", "password")

def verify_export():
    print("=== VERIFY EXPORT ===\n")
    
    # 1. Create test project
    print("1. Create test project...")
    resp = requests.post(f"{API_BASE}/api/projects", json={
        "name": "Export Test Project",
        "description": "Test export functionality",
        "classification": "normal"
    }, auth=AUTH)
    assert resp.status_code == 201, f"Failed to create project: {resp.status_code}"
    project_id = resp.json()["id"]
    print(f"   ✓ Project created: {project_id}")
    
    # 2. Add source
    print("2. Add source...")
    resp = requests.post(f"{API_BASE}/api/projects/{project_id}/sources", json={
        "title": "Test Source",
        "type": "link",
        "comment": "Export test source"
    }, auth=AUTH)
    assert resp.status_code == 201, f"Failed to add source: {resp.status_code}"
    print("   ✓ Source added")
    
    # 3. Add document
    print("3. Add document...")
    files = {"file": ("test.txt", "This is test document content.", "text/plain")}
    resp = requests.post(f"{API_BASE}/api/projects/{project_id}/documents", files=files, auth=AUTH)
    assert resp.status_code == 201, f"Failed to upload document: {resp.status_code}"
    print("   ✓ Document added")
    
    # 4. Add journalist note (should NOT be in export by default)
    print("4. Add journalist note...")
    resp = requests.post(f"{API_BASE}/api/projects/{project_id}/journalist-notes", json={
        "title": "Private Note",
        "body": "This is private and should NOT be exported by default.",
        "category": "raw"
    }, auth=AUTH)
    assert resp.status_code == 201, f"Failed to create note: {resp.status_code}"
    print("   ✓ Journalist note added")
    
    # 5. Export with defaults (notes OFF, metadata ON)
    print("5. Export with defaults (notes=false, metadata=true)...")
    resp = requests.get(f"{API_BASE}/api/projects/{project_id}/export", auth=AUTH)
    assert resp.status_code == 200, f"Export failed: {resp.status_code}"
    export_default = resp.text
    assert "Private Note" not in export_default, "FAIL: Notes leaked in default export!"
    assert "should NOT be exported" not in export_default, "FAIL: Note content leaked!"
    assert "Export Test Project" in export_default, "FAIL: Project name missing"
    assert "Test Source" in export_default, "FAIL: Source missing"
    assert "Status:" in export_default, "FAIL: Status missing (metadata should be ON by default)"
    print("   ✓ Export OK, notes NOT included (correct)")
    
    # 6. Export with metadata=false
    print("6. Export with metadata=false...")
    resp = requests.get(f"{API_BASE}/api/projects/{project_id}/export?include_metadata=false", auth=AUTH)
    assert resp.status_code == 200, f"Export failed: {resp.status_code}"
    export_no_metadata = resp.text
    assert "Status:" not in export_no_metadata, "FAIL: Status leaked when metadata=false!"
    assert "Projekt-ID:" not in export_no_metadata, "FAIL: Project-ID leaked when metadata=false!"
    assert "Test Source" not in export_no_metadata, "FAIL: Sources leaked when metadata=false!"
    assert "*(Ej inkluderat i denna export)*" in export_no_metadata, "FAIL: Missing 'Ej inkluderat' for sources"
    print("   ✓ Export OK, metadata excluded (correct)")
    
    # 7. Export with notes=true
    print("7. Export with notes=true...")
    resp = requests.get(f"{API_BASE}/api/projects/{project_id}/export?include_notes=true", auth=AUTH)
    assert resp.status_code == 200, f"Export failed: {resp.status_code}"
    export_with_notes = resp.text
    assert "Private Note" in export_with_notes, "FAIL: Notes should be included when toggled"
    assert "should NOT be exported by default" in export_with_notes, "FAIL: Note content missing"
    print("   ✓ Export OK, notes included (when toggled)")
    
    # 8. Verify events are clean (metadata only)
    print("8. Verify events are metadata-only...")
    resp = requests.get(f"{API_BASE}/api/projects/{project_id}/events", auth=AUTH)
    assert resp.status_code == 200, f"Failed to fetch events: {resp.status_code}"
    events = resp.json()
    
    export_events = [e for e in events if e["event_type"] == "export_created"]
    assert len(export_events) == 3, f"Expected 3 export events, got {len(export_events)}"
    
    for event in export_events:
        metadata = event.get("event_metadata") or event.get("metadata", {})
        assert "format" in metadata, "FAIL: Missing format in event metadata"
        assert "include_notes" in metadata, "FAIL: Missing include_notes in event metadata"
        
        # Check NO content leaked
        event_str = str(event)
        assert "Private Note" not in event_str, "FAIL: Note title leaked in event!"
        assert "should NOT be exported" not in event_str, "FAIL: Note content leaked in event!"
        assert "test document content" not in event_str, "FAIL: Document content leaked in event!"
    
    print("   ✓ Events are clean (metadata only)")
    
    # 9. Cleanup
    print("9. Cleanup...")
    resp = requests.delete(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
    assert resp.status_code == 204, f"Failed to delete project: {resp.status_code}"
    print("   ✓ Project deleted")
    
    print("\n=== ALL TESTS PASSED (8/8) ===")
    return True

if __name__ == "__main__":
    try:
        verify_export()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
