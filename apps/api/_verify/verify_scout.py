#!/usr/bin/env python3
"""
Verification script for Scout feature.

Tests:
1. GET /api/scout/feeds → triggers lazy seed (2 enabled Polisen feeds)
2. POST /api/scout/fetch → fetch real RSS feeds
3. GET /api/scout/items?hours=24 → verify items returned
4. POST fetch again → verify item count does not increase (dedup)
5. DELETE temp feed (disable)
"""
import sys
import os
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = os.getenv("API_URL", "http://localhost:8000")
AUTH = (os.getenv("AUTH_USER", "admin"), os.getenv("AUTH_PASS", "password"))

os.environ["DEBUG"] = "true"


def check_network():
    """Check if network is available by trying to reach a known endpoint."""
    try:
        response = requests.get("https://www.google.com", timeout=5)
        return True
    except:
        return False


def main():
    print("=" * 70)
    print("SCOUT VERIFICATION (REAL RSS FEEDS)")
    print("=" * 70)
    print()
    
    # Check network availability
    print("Checking network availability...")
    if not check_network():
        print("✗ FAILED: Network unavailable. Cannot test real RSS feeds.")
        print("   This test requires internet connectivity.")
        return 1
    print("✓ Network available")
    print()
    
    passed = 0
    total = 0
    
    # Test 1: GET /api/scout/feeds → triggers lazy seed
    total += 1
    print("1. GET /api/scout/feeds (should trigger lazy seed)...")
    try:
        response = requests.get(
            f"{API_BASE}/api/scout/feeds",
            auth=AUTH
        )
        response.raise_for_status()
        feeds = response.json()
        
        if len(feeds) < 2:
            print(f"✗ FAILED: Expected at least 2 feeds (defaults), got {len(feeds)}")
        else:
            # Check that defaults exist
            default_names = {
                "Polisen – Händelser Västra Götaland",
                "Polisen – Pressmeddelanden Västra Götaland"
            }
            found_names = {f["name"] for f in feeds}
            if not default_names.issubset(found_names):
                print(f"✗ FAILED: Missing default feeds. Found: {found_names}")
            else:
                # Check that both are enabled
                defaults = [f for f in feeds if f["name"] in default_names]
                enabled_count = sum(1 for f in defaults if f["is_enabled"])
                if enabled_count != 2:
                    print(f"✗ FAILED: Expected 2 enabled feeds, got {enabled_count}")
                else:
                    # Check URLs
                    handelser = next((f for f in defaults if "Händelser" in f["name"]), None)
                    press = next((f for f in defaults if "Pressmeddelanden" in f["name"]), None)
                    if not handelser or not handelser["url"]:
                        print(f"✗ FAILED: Händelser feed missing URL")
                    elif not press or not press["url"]:
                        print(f"✗ FAILED: Pressmeddelanden feed missing URL")
                    else:
                        print(f"✓ PASSED: Lazy seed created 2 default feeds (both enabled with URLs)")
                        passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Test 2: POST /api/scout/fetch → fetch real RSS feeds
    total += 1
    print("2. POST /api/scout/fetch (fetch real RSS feeds)...")
    try:
        response = requests.post(
            f"{API_BASE}/api/scout/fetch",
            auth=AUTH,
            timeout=30  # Allow more time for real network requests
        )
        response.raise_for_status()
        result = response.json()
        
        feeds_processed = result.get("feeds_processed", 0)
        results = result.get("results", {})
        
        if feeds_processed == 0:
            print(f"✗ FAILED: No feeds processed")
        elif not results:
            print(f"✗ FAILED: No results returned")
        else:
            # Check that we got results for at least one feed
            total_items = sum(results.values())
            if total_items == 0:
                print(f"⚠ WARNING: Fetch succeeded but no new items found (feeds may be empty or all items already exist)")
            else:
                print(f"✓ PASSED: Fetch processed {feeds_processed} feeds, created {total_items} new items")
            passed += 1
    except requests.exceptions.Timeout:
        print(f"✗ FAILED: Request timeout (network may be slow)")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Test 3: GET /api/scout/items?hours=24
    total += 1
    print("3. GET /api/scout/items?hours=24...")
    initial_count = 0
    try:
        response = requests.get(
            f"{API_BASE}/api/scout/items?hours=24",
            auth=AUTH
        )
        response.raise_for_status()
        items = response.json()
        initial_count = len(items)
        
        # Verify items have required fields
        required_fields = {"id", "title", "link", "raw_source", "fetched_at"}
        all_valid = all(
            all(field in item for field in required_fields)
            for item in items
        )
        if not all_valid:
            print(f"✗ FAILED: Missing required fields in items")
        else:
            print(f"✓ PASSED: Got {initial_count} items with required fields")
            passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Test 4: POST fetch again → verify dedup
    total += 1
    print("4. POST fetch again (should not create duplicates)...")
    try:
        response = requests.post(
            f"{API_BASE}/api/scout/fetch",
            auth=AUTH,
            timeout=30
        )
        response.raise_for_status()
        
        # Get items again
        response2 = requests.get(
            f"{API_BASE}/api/scout/items?hours=24",
            auth=AUTH
        )
        response2.raise_for_status()
        items_after = response2.json()
        new_count = len(items_after)
        
        if new_count > initial_count:
            print(f"✗ FAILED: Item count increased ({initial_count} → {new_count}), dedup failed")
        else:
            print(f"✓ PASSED: Item count unchanged or decreased ({initial_count} → {new_count}), dedup works")
            passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Test 5: Create and delete a test feed
    total += 1
    print("5. Create and delete test feed...")
    temp_feed_id = None
    try:
        # Create test feed with a real RSS URL (using a simple test feed)
        response = requests.post(
            f"{API_BASE}/api/scout/feeds",
            json={
                "name": "Test Feed (Verification)",
                "url": "https://www.w3.org/2005/Atom"  # Atom spec as test (will fail but tests the flow)
            },
            auth=AUTH
        )
        response.raise_for_status()
        temp_feed = response.json()
        temp_feed_id = temp_feed["id"]
        
        if not temp_feed["is_enabled"]:
            print(f"✗ FAILED: Feed should be enabled")
        else:
            # Delete (disable) the feed
            response2 = requests.delete(
                f"{API_BASE}/api/scout/feeds/{temp_feed_id}",
                auth=AUTH
            )
            response2.raise_for_status()
            
            # Verify feed is disabled
            response3 = requests.get(
                f"{API_BASE}/api/scout/feeds",
                auth=AUTH
            )
            response3.raise_for_status()
            feeds = response3.json()
            feed = next((f for f in feeds if f["id"] == temp_feed_id), None)
            
            if not feed:
                print(f"✗ FAILED: Feed not found after delete")
            elif feed["is_enabled"]:
                print(f"✗ FAILED: Feed should be disabled")
            else:
                print(f"✓ PASSED: Feed created and disabled successfully")
                passed += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
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
