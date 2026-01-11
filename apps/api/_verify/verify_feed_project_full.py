#!/usr/bin/env python3
"""
Verification script for full feed import functionality.
Tests: Project creation with description/tags, ProjectSource with URL,
ProjectNote with fulltext, Document creation, and idempotency.
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import models
from models import Project, Document, ProjectNote, ProjectSource
import os
# Get DB URL from environment or default
def get_db_url():
    return os.getenv("DATABASE_URL", "postgresql://arbetsytan:arbetsytan@localhost:5432/arbetsytan")

# Test configuration
BASE_URL = "http://localhost:8000"
AUTH = ("admin", "password")
TEST_RESULTS_DIR = Path(__file__).parent.parent.parent / "test_results"
TEST_RESULTS_DIR.mkdir(exist_ok=True)

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures"
SAMPLE_RSS = FIXTURES_DIR / "sample.rss"
SAMPLE_ARTICLE = FIXTURES_DIR / "sample_article.html"


def mock_fetch_url_bytes(url: str) -> tuple[bytes, str]:
    """
    Mock fetch_url_bytes for testing.
    Returns fixture content based on URL.
    """
    if "feed" in url.lower() or url.endswith(".rss") or url.endswith(".xml"):
        # Return RSS fixture
        with open(SAMPLE_RSS, 'rb') as f:
            return (f.read(), "application/rss+xml")
    elif "article" in url.lower() or "polisen.se" in url:
        # Return article HTML fixture
        with open(SAMPLE_ARTICLE, 'rb') as f:
            return (f.read(), "text/html")
    else:
        raise ValueError(f"Unknown URL in mock: {url}")


def patch_feeds_module():
    """
    Patch feeds module to use mocked fetch.
    """
    import feeds
    original_validate_and_fetch = feeds.validate_and_fetch
    
    def mock_validate_and_fetch(url: str, timeout=10, max_bytes=5*1024*1024):
        return mock_fetch_url_bytes(url)
    
    feeds.validate_and_fetch = mock_validate_and_fetch
    feeds.fetch_feed_url = lambda url: mock_fetch_url_bytes(url)[0]
    
    return original_validate_and_fetch


def test_preview():
    """Test feed preview endpoint."""
    print("Testing GET /api/feeds/preview...")
    
    response = requests.get(
        f"{BASE_URL}/api/feeds/preview",
        params={"url": "https://test.feed.rss"},
        auth=AUTH
    )
    
    assert response.status_code == 200, f"Preview failed: {response.status_code} - {response.text}"
    data = response.json()
    
    assert "title" in data, "Missing title in preview"
    assert "items" in data, "Missing items in preview"
    assert len(data["items"]) == 3, f"Expected 3 items, got {len(data['items'])}"
    assert data["title"] == "Polisen – Västra Götaland", f"Wrong title: {data['title']}"
    
    print("✓ Preview test passed")
    return data


def test_create_project_from_feed():
    """Test creating project from feed with fulltext."""
    print("Testing POST /api/projects/from-feed (fulltext mode)...")
    
    # Generate unique project name
    project_name = f"Test Feed Import {datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    response = requests.post(
        f"{BASE_URL}/api/projects/from-feed",
        json={
            "url": "https://test.feed.rss",
            "project_name": project_name,
            "limit": 3,
            "mode": "fulltext"
        },
        auth=AUTH
    )
    
    assert response.status_code == 201, f"Create failed: {response.status_code} - {response.text}"
    data = response.json()
    
    assert "project_id" in data, "Missing project_id in response"
    assert "created_count" in data, "Missing created_count"
    assert "created_notes" in data, "Missing created_notes"
    assert "created_sources" in data, "Missing created_sources"
    assert "skipped_duplicates" in data, "Missing skipped_duplicates"
    
    print(f"✓ Created project {data['project_id']}")
    print(f"  Documents: {data['created_count']}, Notes: {data['created_notes']}, Sources: {data['created_sources']}")
    
    return data


def get_db_url():
    """Get database URL from environment or default."""
    return os.getenv("DATABASE_URL", "postgresql://arbetsytan:arbetsytan@postgres:5432/arbetsytan")


def verify_database(project_id: int, expected_items: int):
    """Verify database state."""
    print(f"Verifying database for project {project_id}...")
    
    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Check project
        project = db.query(Project).filter(Project.id == project_id).first()
        assert project is not None, f"Project {project_id} not found"
        assert "Imported from RSS feed" in project.description, "Project description missing"
        assert project.tags is not None, "Project tags missing"
        assert "rss" in project.tags, "Missing 'rss' tag"
        assert "polisen" in project.tags, "Missing 'polisen' tag"
        assert "västra-götaland" in project.tags, "Missing region tag"
        print("✓ Project verified")
        
        # Check documents
        documents = db.query(Document).filter(Document.project_id == project_id).all()
        assert len(documents) == expected_items, f"Expected {expected_items} documents, got {len(documents)}"
        for doc in documents:
            assert doc.masked_text is not None, "Document missing masked_text"
            assert doc.sanitize_level is not None, "Document missing sanitize_level"
            assert doc.document_metadata is not None, "Document missing metadata"
            assert doc.document_metadata.get("source_type") == "feed", "Wrong source_type"
        print(f"✓ {len(documents)} Documents verified")
        
        # Check ProjectNotes
        notes = db.query(ProjectNote).filter(ProjectNote.project_id == project_id).all()
        assert len(notes) == expected_items, f"Expected {expected_items} notes, got {len(notes)}"
        for note in notes:
            assert note.masked_body is not None, "Note missing masked_body"
            assert note.sanitize_level is not None, "Note missing sanitize_level"
            assert note.usage_restrictions is not None, "Note missing usage_restrictions"
        print(f"✓ {len(notes)} ProjectNotes verified")
        
        # Check ProjectSources
        sources = db.query(ProjectSource).filter(ProjectSource.project_id == project_id).all()
        assert len(sources) == expected_items, f"Expected {expected_items} sources, got {len(sources)}"
        for source in sources:
            assert source.url is not None, "Source missing url"
            assert source.url.startswith("https://"), "Source URL invalid"
        print(f"✓ {len(sources)} ProjectSources verified")
        
    finally:
        db.close()


def test_idempotency(project_id: int, feed_url: str):
    """Test that re-importing same feed is idempotent."""
    print("Testing idempotency (re-import)...")
    
    # Get project name
    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    db = Session()
    project = db.query(Project).filter(Project.id == project_id).first()
    project_name = project.name
    db.close()
    
    response = requests.post(
        f"{BASE_URL}/api/projects/from-feed",
        json={
            "url": feed_url,
            "project_name": project_name,
            "limit": 3,
            "mode": "fulltext"
        },
        auth=AUTH
    )
    
    assert response.status_code == 201, f"Re-import failed: {response.status_code}"
    data = response.json()
    
    assert data["created_count"] == 0, f"Expected 0 new documents, got {data['created_count']}"
    assert data["created_notes"] == 0, f"Expected 0 new notes, got {data['created_notes']}"
    assert data["created_sources"] == 0, f"Expected 0 new sources, got {data['created_sources']}"
    assert data["skipped_duplicates"] == 3, f"Expected 3 skipped, got {data['skipped_duplicates']}"
    
    print("✓ Idempotency test passed")
    return data


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Feed Import Full Verification")
    print("=" * 60)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    try:
        # Patch feeds module for testing
        original = patch_feeds_module()
        
        # Test preview
        preview_data = test_preview()
        results["tests"]["preview"] = {"status": "PASS", "data": preview_data}
        
        # Test create project
        create_data = test_create_project_from_feed()
        project_id = create_data["project_id"]
        results["tests"]["create_project"] = {"status": "PASS", "data": create_data}
        
        # Verify database
        verify_database(project_id, expected_items=3)
        results["tests"]["database_verification"] = {"status": "PASS"}
        
        # Test idempotency
        idempotency_data = test_idempotency(project_id, "https://test.feed.rss")
        results["tests"]["idempotency"] = {"status": "PASS", "data": idempotency_data}
        
        results["overall_status"] = "PASS"
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        
    except Exception as e:
        results["overall_status"] = "FAIL"
        results["error"] = str(e)
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        # Restore original function
        if 'original' in locals():
            import feeds
            feeds.validate_and_fetch = original
    
    # Write results
    output_file = TEST_RESULTS_DIR / "feed_project_full_verify.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults written to: {output_file}")
    return results


if __name__ == "__main__":
    main()