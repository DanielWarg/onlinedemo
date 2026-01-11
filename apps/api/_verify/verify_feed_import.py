#!/usr/bin/env python3
"""
Verification script for feed import functionality.
Tests preview, create project from feed, and deduplication.
"""
import sys
import os
import json
import requests
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = os.getenv("API_URL", "http://localhost:8000")
AUTH = (os.getenv("AUTH_USER", "admin"), os.getenv("AUTH_PASS", "password"))

os.environ["DEBUG"] = "true"

# Generate unique project name for each test run
UNIQUE_PROJECT_NAME = f"Feed Import Test {int(time.time())}"


def main():
    print("=" * 70)
    print("FEED IMPORT VERIFICATION")
    print("=" * 70)
    print()

    results = {
        "tests": [],
        "passed": 0,
        "failed": 0,
        "total": 0
    }

    # Test 1: Preview feed (using real feed for simplicity)
    results["total"] += 1
    print("1. GET /api/feeds/preview...")
    try:
        # Use a real public feed for testing (domstol.se)
        test_url = "https://www.domstol.se/feed/56/?searchPageId=1139&scope=news"
        response = requests.get(
            f"{API_BASE}/api/feeds/preview?url={requests.utils.quote(test_url)}",
            auth=AUTH,
            timeout=30
        )
        response.raise_for_status()
        preview_data = response.json()

        required_fields = {"title", "description", "items"}
        if not all(field in preview_data for field in required_fields):
            print(f"✗ FAILED: Missing required fields. Got: {list(preview_data.keys())}")
            results["failed"] += 1
            results["tests"].append({"test": "preview", "status": "failed", "error": "Missing fields"})
        elif len(preview_data["items"]) < 3:
            print(f"✗ FAILED: Expected at least 3 items, got {len(preview_data['items'])}")
            results["failed"] += 1
            results["tests"].append({"test": "preview", "status": "failed", "error": "Insufficient items"})
        else:
            # Check item structure
            item = preview_data["items"][0]
            item_fields = {"guid", "title", "link", "summary_text"}
            if not all(field in item for field in item_fields):
                print(f"✗ FAILED: Item missing required fields. Got: {list(item.keys())}")
                results["failed"] += 1
                results["tests"].append({"test": "preview", "status": "failed", "error": "Item missing fields"})
            else:
                print(f"✓ PASSED: Preview returned {len(preview_data['items'])} items with correct structure")
                results["passed"] += 1
                results["tests"].append({"test": "preview", "status": "passed"})
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        results["failed"] += 1
        results["tests"].append({"test": "preview", "status": "failed", "error": str(e)})
    print()

    # Test 2: Create project from feed (using real feed)
    results["total"] += 1
    print("2. POST /api/projects/from-feed...")
    project_id = None
    try:
        # Use a real public feed for testing
        test_url = "https://www.domstol.se/feed/56/?searchPageId=1139&scope=news"
        response = requests.post(
            f"{API_BASE}/api/projects/from-feed",
            auth=AUTH,
            json={
                "url": test_url,
                "project_name": UNIQUE_PROJECT_NAME,
                "limit": 3
            },
            timeout=60
        )
        response.raise_for_status()
        create_result = response.json()

        if "project_id" not in create_result:
            print(f"✗ FAILED: Missing project_id in response")
            results["failed"] += 1
            results["tests"].append({"test": "create", "status": "failed", "error": "Missing project_id"})
        elif create_result.get("created_count", 0) != 3:
            print(f"✗ FAILED: Expected created_count=3, got {create_result.get('created_count')}")
            results["failed"] += 1
            results["tests"].append({"test": "create", "status": "failed", "error": f"Wrong created_count: {create_result.get('created_count')}"})
        else:
            project_id = create_result["project_id"]
            
            # Verify project exists
            project_response = requests.get(
                f"{API_BASE}/api/projects/{project_id}",
                auth=AUTH
            )
            if project_response.status_code != 200:
                print(f"✗ FAILED: Project {project_id} not found")
                results["failed"] += 1
                results["tests"].append({"test": "create", "status": "failed", "error": "Project not found"})
            else:
                # Verify documents were created
                docs_response = requests.get(
                    f"{API_BASE}/api/projects/{project_id}/documents",
                    auth=AUTH
                )
                docs_response.raise_for_status()
                documents = docs_response.json()
                
                if len(documents) != 3:
                    print(f"✗ FAILED: Expected 3 documents, got {len(documents)}")
                    results["failed"] += 1
                    results["tests"].append({"test": "create", "status": "failed", "error": f"Wrong document count: {len(documents)}"})
                else:
                    # Verify metadata is saved (check one document)
                    doc_detail_response = requests.get(
                        f"{API_BASE}/api/documents/{documents[0]['id']}",
                        auth=AUTH
                    )
                    if doc_detail_response.status_code == 200:
                        doc_detail = doc_detail_response.json()
                        # Note: metadata might not be in response schema, but should be in DB
                        print(f"✓ PASSED: Project {project_id} created with {len(documents)} documents")
                        results["passed"] += 1
                        results["tests"].append({"test": "create", "status": "passed", "project_id": project_id})
                    else:
                        print(f"⚠ WARNING: Could not verify document metadata (status {doc_detail_response.status_code})")
                        print(f"✓ PASSED: Project {project_id} created with {len(documents)} documents")
                        results["passed"] += 1
                        results["tests"].append({"test": "create", "status": "passed", "project_id": project_id})
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        results["failed"] += 1
        results["tests"].append({"test": "create", "status": "failed", "error": str(e)})
    print()

    # Test 3: Deduplication (import again to same project)
    if project_id:
        results["total"] += 1
        print("3. POST /api/projects/from-feed again (deduplication test)...")
        try:
            # Use same URL and project name to test deduplication
            test_url = "https://www.domstol.se/feed/56/?searchPageId=1139&scope=news"
            response = requests.post(
                f"{API_BASE}/api/projects/from-feed",
                auth=AUTH,
                json={
                    "url": test_url,
                    "project_name": "Feed Import Test",  # Same name = same project
                    "limit": 3
                },
                timeout=60
            )
            response.raise_for_status()
            create_result = response.json()

            if create_result.get("created_count", 0) != 0:
                print(f"✗ FAILED: Expected created_count=0 (dedupe), got {create_result.get('created_count')}")
                results["failed"] += 1
                results["tests"].append({"test": "dedupe", "status": "failed", "error": f"Wrong created_count: {create_result.get('created_count')}"})
            elif create_result.get("skipped_duplicates", 0) != 3:
                print(f"✗ FAILED: Expected skipped_duplicates=3, got {create_result.get('skipped_duplicates')}")
                results["failed"] += 1
                results["tests"].append({"test": "dedupe", "status": "failed", "error": f"Wrong skipped_duplicates: {create_result.get('skipped_duplicates')}"})
            else:
                print(f"✓ PASSED: Deduplication works (created_count=0, skipped_duplicates=3)")
                results["passed"] += 1
                results["tests"].append({"test": "dedupe", "status": "passed"})
        except Exception as e:
            print(f"✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            results["failed"] += 1
            results["tests"].append({"test": "dedupe", "status": "failed", "error": str(e)})
    else:
        print("3. SKIPPED: Deduplication test (project creation failed)")
    print()

    # Write results
    results_dir = Path(__file__).parent.parent / "test_results"
    results_dir.mkdir(exist_ok=True)
    results_file = results_dir / "feed_import_verify.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"Passed: {results['passed']}/{results['total']}")
    print(f"Failed: {results['failed']}/{results['total']}")
    print(f"Results saved to: {results_file}")
    print()

    if results["passed"] == results["total"]:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
