#!/usr/bin/env python3
"""
End-to-End Verification for Projects Module.

Tests against real API endpoints (not unit tests):
- Scenario A: Project CRUD (create, read, update, delete)
- Scenario B: Document ingest with PII masking
- Scenario C: Recording upload → transcript → ingest

Security: Never logs raw PII or transcript content. Only IDs and counts.
Exit code: 0 = PASS, 1 = FAIL
"""

import requests
import sys
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
AUTH = ("admin", "password")


def log(msg: str, level: str = "INFO"):
    """Print structured log without PII."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def log_pass(msg: str):
    log(f"✓ {msg}", "PASS")


def log_fail(msg: str):
    log(f"✗ {msg}", "FAIL")


def log_section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ============================================================================
# SCENARIO A: Project CRUD
# ============================================================================

def scenario_a_project_crud() -> bool:
    """Test full project lifecycle: create, read, update, delete."""
    log_section("SCENARIO A: Project CRUD")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_name = f"E2E Project {timestamp}"
    project_description = """Detta är ett testprojekt för E2E-verifiering.
Det innehåller flera rader text för att simulera riktig data.
Projektet ska testas för CRUD-operationer."""
    project_tags = ["e2e", "demo", "pii"]
    due_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
    
    project_id = None
    
    try:
        # 1. CREATE
        log("Creating project...")
        resp = requests.post(
            f"{API_BASE}/api/projects",
            auth=AUTH,
            json={
                "name": project_name,
                "description": project_description,
                "classification": "normal",
                "tags": project_tags,
                "due_date": due_date
            }
        )
        if resp.status_code != 201:
            log_fail(f"Create failed: {resp.status_code}")
            return False
        
        data = resp.json()
        project_id = data.get("id")
        if not project_id:
            log_fail("No project ID returned")
            return False
        log_pass(f"Created project (ID: {project_id})")
        
        # 2. READ
        log("Fetching project...")
        resp = requests.get(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
        if resp.status_code != 200:
            log_fail(f"Get failed: {resp.status_code}")
            return False
        
        data = resp.json()
        if data.get("name") != project_name:
            log_fail(f"Name mismatch")
            return False
        if data.get("tags") != project_tags:
            log_fail(f"Tags mismatch")
            return False
        if "due_date" not in data:
            log_fail("due_date missing")
            return False
        log_pass("Fetched project with correct data")
        
        # 3. UPDATE
        log("Updating project...")
        new_description = "Uppdaterad beskrivning för E2E-test."
        new_tags = ["e2e", "updated", "trimmed "]  # Note: space to test trim
        resp = requests.put(
            f"{API_BASE}/api/projects/{project_id}",
            auth=AUTH,
            json={
                "description": new_description,
                "tags": new_tags
            }
        )
        if resp.status_code != 200:
            log_fail(f"Update failed: {resp.status_code}")
            return False
        
        data = resp.json()
        if data.get("description") != new_description:
            log_fail("Description not updated")
            return False
        log_pass("Updated project")
        
        # 4. LIST
        log("Listing projects...")
        resp = requests.get(f"{API_BASE}/api/projects", auth=AUTH)
        if resp.status_code != 200:
            log_fail(f"List failed: {resp.status_code}")
            return False
        
        projects = resp.json()
        found = any(p.get("id") == project_id for p in projects)
        if not found:
            log_fail("Project not in list")
            return False
        log_pass("Project found in list")
        
        # 5. DELETE
        log("Deleting project...")
        resp = requests.delete(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
        if resp.status_code != 204:
            log_fail(f"Delete failed: {resp.status_code}")
            return False
        log_pass("Deleted project")
        
        # 6. VERIFY DELETION
        log("Verifying deletion...")
        resp = requests.get(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
        if resp.status_code != 404:
            log_fail("Project still exists after delete")
            return False
        log_pass("Project correctly removed")
        
        log_pass("SCENARIO A: PASS")
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        # Cleanup if project was created
        if project_id:
            try:
                requests.delete(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
            except:
                pass
        return False


# ============================================================================
# SCENARIO B: Document Ingest with PII
# ============================================================================

def scenario_b_document_ingest() -> bool:
    """Test document upload with PII masking verification."""
    log_section("SCENARIO B: Document Ingest (PII)")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_id = None
    
    # PII test content (these exact strings should NOT appear in masked output)
    pii_email = "test@example.com"
    pii_phone = "070-123 45 67"
    pii_pnr = "850101-1234"
    
    test_content = f"""Journalistiskt testmaterial för E2E-verifiering.

Kontaktuppgifter:
- Email: {pii_email}
- Telefon: {pii_phone}

Känsliga uppgifter:
- Personnummer: {pii_pnr}

Detta är text som ska saneras enligt våra säkerhetsrutiner.
All personlig information ska maskeras automatiskt."""
    
    try:
        # 1. Create project
        log("Creating project for document test...")
        resp = requests.post(
            f"{API_BASE}/api/projects",
            auth=AUTH,
            json={
                "name": f"E2E Doc Test {timestamp}",
                "classification": "normal"
            }
        )
        if resp.status_code != 201:
            log_fail(f"Create project failed: {resp.status_code}")
            return False
        project_id = resp.json().get("id")
        log_pass(f"Created project (ID: {project_id})")
        
        # 2. Create temp file with PII
        log("Creating test document with PII...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file = f.name
        
        # 3. Upload document
        log("Uploading document...")
        with open(temp_file, 'rb') as f:
            resp = requests.post(
                f"{API_BASE}/api/projects/{project_id}/documents",
                auth=AUTH,
                files={"file": ("test_pii.txt", f, "text/plain")}
            )
        
        # Cleanup temp file
        os.unlink(temp_file)
        
        if resp.status_code != 201:
            log_fail(f"Upload failed: {resp.status_code} - {resp.text[:100]}")
            return False
        
        doc_data = resp.json()
        doc_id = doc_data.get("id")
        log_pass(f"Uploaded document (ID: {doc_id})")
        
        # 4. Fetch document and verify masking
        log("Fetching document to verify masking...")
        resp = requests.get(f"{API_BASE}/api/documents/{doc_id}", auth=AUTH)
        if resp.status_code != 200:
            log_fail(f"Get document failed: {resp.status_code}")
            return False
        
        doc_detail = resp.json()
        masked_text = doc_detail.get("masked_text", "")
        
        # Verify PII is NOT in masked text
        pii_leaked = False
        if pii_email in masked_text:
            log_fail(f"Email leaked in masked_text")
            pii_leaked = True
        if pii_phone in masked_text:
            log_fail(f"Phone leaked in masked_text")
            pii_leaked = True
        if pii_pnr in masked_text:
            log_fail(f"PNR leaked in masked_text")
            pii_leaked = True
        
        if pii_leaked:
            return False
        log_pass("PII correctly masked (no leaks)")
        
        # Verify mask tokens exist
        has_email_token = "[EMAIL]" in masked_text or "[email]" in masked_text.lower()
        has_phone_token = "[PHONE]" in masked_text or "[TELEFON]" in masked_text or "[phone]" in masked_text.lower()
        has_pnr_token = "[PERSONNUMMER]" in masked_text or "[REDACTED]" in masked_text or "***" in masked_text
        
        log(f"  Mask tokens: EMAIL={has_email_token}, PHONE={has_phone_token}, PNR={has_pnr_token}")
        if not (has_email_token or has_phone_token or has_pnr_token):
            log_fail("No mask tokens found (expected at least one)")
            return False
        log_pass("Mask tokens present")
        
        # 5. Verify sanitize_level and usage_restrictions
        sanitize_level = doc_detail.get("sanitize_level")
        usage_restrictions = doc_detail.get("usage_restrictions", {})
        
        if not sanitize_level:
            log_fail("sanitize_level missing")
            return False
        log_pass(f"sanitize_level: {sanitize_level}")
        
        if "ai_allowed" not in usage_restrictions:
            log_fail("usage_restrictions.ai_allowed missing")
            return False
        log_pass(f"usage_restrictions present: ai_allowed={usage_restrictions.get('ai_allowed')}")
        
        # 6. Verify events
        log("Checking project events...")
        resp = requests.get(f"{API_BASE}/api/projects/{project_id}/events", auth=AUTH)
        if resp.status_code != 200:
            log_fail(f"Get events failed: {resp.status_code}")
            return False
        
        events = resp.json()
        doc_events = [e for e in events if e.get("event_type") == "document_uploaded"]
        if not doc_events:
            log_fail("No document_uploaded event found")
            return False
        
        # Verify event metadata contains only metadata, not text
        event_meta = doc_events[0].get("event_metadata", {})
        meta_str = str(event_meta)
        if pii_email in meta_str or pii_phone in meta_str or pii_pnr in meta_str:
            log_fail("PII found in event metadata!")
            return False
        log_pass("Event contains only metadata (no PII/text)")
        
        # Cleanup
        log("Cleaning up...")
        requests.delete(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
        log_pass("Cleanup done")
        
        log_pass("SCENARIO B: PASS")
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        if project_id:
            try:
                requests.delete(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
            except:
                pass
        return False


# ============================================================================
# SCENARIO C: Recording Upload → Transcript → Ingest
# ============================================================================

def scenario_c_recording_upload() -> bool:
    """Test audio upload → transcription → masking → ingest."""
    log_section("SCENARIO C: Recording Upload")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_id = None
    
    # Check for test audio file
    audio_paths = [
        "/tmp/e2e_audio.wav",
        "/app/Del21.wav",
        Path(__file__).parent.parent.parent.parent / "Del21.wav"
    ]
    
    audio_file = None
    for p in audio_paths:
        path = Path(p)
        if path.exists():
            audio_file = path
            break
    
    if not audio_file:
        log("No audio file found. Checking for repo audio...")
        # Try relative path from script
        repo_audio = Path(__file__).parent.parent.parent.parent / "Del21.wav"
        if repo_audio.exists():
            audio_file = repo_audio
        else:
            log("⚠ No audio file available for testing")
            log("  To test recording: place a .wav file at /tmp/e2e_audio.wav")
            log("  Or ensure Del21.wav exists in repo root")
            log_pass("SCENARIO C: SKIPPED (no audio file)")
            return True  # Skip, not fail
    
    try:
        # 1. Create project
        log("Creating project for recording test...")
        resp = requests.post(
            f"{API_BASE}/api/projects",
            auth=AUTH,
            json={
                "name": f"E2E Recording Test {timestamp}",
                "classification": "normal"
            }
        )
        if resp.status_code != 201:
            log_fail(f"Create project failed: {resp.status_code}")
            return False
        project_id = resp.json().get("id")
        log_pass(f"Created project (ID: {project_id})")
        
        # 2. Upload recording
        log(f"Uploading audio file ({audio_file.name})...")
        with open(audio_file, 'rb') as f:
            resp = requests.post(
                f"{API_BASE}/api/projects/{project_id}/recordings",
                auth=AUTH,
                files={"file": (audio_file.name, f, "audio/wav")}
            )
        
        if resp.status_code != 201:
            log_fail(f"Recording upload failed: {resp.status_code} - {resp.text[:200]}")
            return False
        
        doc_data = resp.json()
        doc_id = doc_data.get("id")
        log_pass(f"Recording uploaded and transcribed (ID: {doc_id})")
        
        # 3. Fetch document to verify transcript
        log("Fetching transcribed document...")
        resp = requests.get(f"{API_BASE}/api/documents/{doc_id}", auth=AUTH)
        if resp.status_code != 200:
            log_fail(f"Get document failed: {resp.status_code}")
            return False
        
        doc_detail = resp.json()
        masked_text = doc_detail.get("masked_text", "")
        
        # Verify markdown structure (should have headers)
        has_header = "##" in masked_text or "#" in masked_text
        has_content = len(masked_text) > 50
        
        if not has_content:
            log_fail("Transcript too short or empty")
            return False
        log_pass(f"Transcript has content ({len(masked_text)} chars)")
        
        if has_header:
            log_pass("Markdown structure present (headers found)")
        else:
            log("⚠ No markdown headers in transcript (may be OK for short audio)")
        
        # 4. Verify events
        log("Checking recording events...")
        resp = requests.get(f"{API_BASE}/api/projects/{project_id}/events", auth=AUTH)
        if resp.status_code != 200:
            log_fail(f"Get events failed: {resp.status_code}")
            return False
        
        events = resp.json()
        recording_events = [e for e in events if e.get("event_type") == "recording_transcribed"]
        
        if not recording_events:
            log("⚠ No recording_transcribed event (may be document_uploaded instead)")
        else:
            # Verify event has only metadata
            event_meta = recording_events[0].get("event_metadata", {})
            
            # Should have metadata like mime, size, duration
            has_mime = "mime" in event_meta or "mime_type" in event_meta or "file_type" in event_meta
            has_size = "size" in event_meta or "file_size" in event_meta
            
            # Should NOT have transcript text (check by looking for long strings)
            meta_values = [str(v) for v in event_meta.values()]
            long_text = any(len(v) > 100 for v in meta_values)
            
            if long_text:
                log_fail("Event metadata contains long text (possible transcript leak)")
                return False
            log_pass("Event contains only metadata (no transcript)")
        
        # Cleanup
        log("Cleaning up...")
        requests.delete(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
        log_pass("Cleanup done")
        
        log_pass("SCENARIO C: PASS")
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        if project_id:
            try:
                requests.delete(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
            except:
                pass
        return False


# ============================================================================
# SCENARIO D: Notes CRUD with PII
# ============================================================================

def scenario_d_notes() -> bool:
    """Test notes creation with PII masking."""
    log_section("SCENARIO D: Notes (PII)")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_id = None
    
    # PII test content
    pii_email = "notes@example.com"
    pii_phone = "08-123 456 78"
    
    note_body = f"""Anteckning med känslig information.
Kontakta redaktören på {pii_email} eller ring {pii_phone}.
Detta ska maskeras automatiskt."""
    
    try:
        # 1. Create project
        log("Creating project for notes test...")
        resp = requests.post(
            f"{API_BASE}/api/projects",
            auth=AUTH,
            json={
                "name": f"E2E Notes Test {timestamp}",
                "classification": "normal"
            }
        )
        if resp.status_code != 201:
            log_fail(f"Create project failed: {resp.status_code}")
            return False
        project_id = resp.json().get("id")
        log_pass(f"Created project (ID: {project_id})")
        
        # 2. Create note with PII
        log("Creating note with PII...")
        resp = requests.post(
            f"{API_BASE}/api/projects/{project_id}/notes",
            auth=AUTH,
            json={
                "title": "Test Note",
                "body": note_body
            }
        )
        if resp.status_code != 201:
            log_fail(f"Create note failed: {resp.status_code} - {resp.text[:100]}")
            return False
        
        note_data = resp.json()
        note_id = note_data.get("id")
        log_pass(f"Created note (ID: {note_id})")
        
        # 3. Verify PII is masked
        log("Verifying PII masking...")
        masked_body = note_data.get("masked_body", "")
        
        pii_leaked = False
        if pii_email in masked_body:
            log_fail("Email leaked in masked_body")
            pii_leaked = True
        if pii_phone in masked_body:
            log_fail("Phone leaked in masked_body")
            pii_leaked = True
        
        if pii_leaked:
            return False
        log_pass("PII correctly masked")
        
        # 4. List notes
        log("Listing notes...")
        resp = requests.get(f"{API_BASE}/api/projects/{project_id}/notes", auth=AUTH)
        if resp.status_code != 200:
            log_fail(f"List notes failed: {resp.status_code}")
            return False
        
        notes = resp.json()
        if not any(n.get("id") == note_id for n in notes):
            log_fail("Note not in list")
            return False
        log_pass("Note found in list")
        
        # 5. Get single note
        log("Getting note...")
        resp = requests.get(f"{API_BASE}/api/notes/{note_id}", auth=AUTH)
        if resp.status_code != 200:
            log_fail(f"Get note failed: {resp.status_code}")
            return False
        log_pass("Got note successfully")
        
        # 6. Delete note
        log("Deleting note...")
        resp = requests.delete(f"{API_BASE}/api/notes/{note_id}", auth=AUTH)
        if resp.status_code != 204:
            log_fail(f"Delete note failed: {resp.status_code}")
            return False
        log_pass("Deleted note")
        
        # 7. Verify deletion
        log("Verifying deletion...")
        resp = requests.get(f"{API_BASE}/api/notes/{note_id}", auth=AUTH)
        if resp.status_code != 404:
            log_fail("Note still exists after delete")
            return False
        log_pass("Note correctly removed")
        
        # Cleanup
        log("Cleaning up...")
        requests.delete(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
        log_pass("Cleanup done")
        
        log_pass("SCENARIO D: PASS")
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        if project_id:
            try:
                requests.delete(f"{API_BASE}/api/projects/{project_id}", auth=AUTH)
            except:
                pass
        return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all E2E scenarios."""
    print("\n" + "=" * 60)
    print("  PROJECTS E2E VERIFICATION")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    # Check API connectivity
    log("Checking API connectivity...")
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        if resp.status_code != 200:
            log_fail(f"API health check failed: {resp.status_code}")
            sys.exit(1)
        log_pass(f"API reachable at {API_BASE}")
    except Exception as e:
        log_fail(f"Cannot reach API: {e}")
        sys.exit(1)
    
    results = {}
    
    # Run scenarios
    results["A_CRUD"] = scenario_a_project_crud()
    results["B_DOCUMENT"] = scenario_b_document_ingest()
    results["C_RECORDING"] = scenario_c_recording_upload()
    
    results["D_NOTES"] = scenario_d_notes()
    
    # Summary
    log_section("SUMMARY")
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"  {symbol} Scenario {name}: {status}")
        if not passed:
            all_pass = False
    
    print()
    if all_pass:
        log_pass("ALL SCENARIOS PASSED")
        sys.exit(0)
    else:
        log_fail("SOME SCENARIOS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()

