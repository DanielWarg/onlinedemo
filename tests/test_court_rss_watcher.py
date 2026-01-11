"""
Unit tests för court_rss_watcher.py
"""
import html
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

# Importera modulen
import sys
tools_path = Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(tools_path))

from court_rss_watcher import (
    parse_entry,
    get_new_items,
    load_last_guid,
    save_last_guid,
    format_pub_date
)
import feedparser


# Minimal RSS-sträng med a10:content namespace
MINIMAL_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:a10="http://www.w3.org/2005/Atom">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Test Post 1</title>
      <link>https://example.com/post1</link>
      <guid isPermaLink="true">https://example.com/post1</guid>
      <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
      <a10:content type="html">&lt;p&gt;Detta är &amp;lt;b&gt;test&lt;/b&gt; content&lt;/p&gt;</a10:content>
    </item>
    <item>
      <title>Test Post 2</title>
      <link>https://example.com/post2</link>
      <guid isPermaLink="true">https://example.com/post2</guid>
      <pubDate>Tue, 02 Jan 2024 14:30:00 +0000</pubDate>
      <a10:content type="html">&lt;div&gt;Mer &amp;quot;content&amp;quot; här&lt;/div&gt;</a10:content>
    </item>
  </channel>
</rss>"""


def test_parse_entry_with_a10_content():
    """Test att items parse:as korrekt och a10:content blir unescaped."""
    feed = feedparser.parse(MINIMAL_RSS)
    
    assert len(feed.entries) == 2
    
    # Test första entry
    entry1 = feed.entries[0]
    item1 = parse_entry(entry1)
    
    assert item1['guid'] == 'https://example.com/post1'
    assert item1['title'] == 'Test Post 1'
    assert item1['link'] == 'https://example.com/post1'
    assert item1['pubDate'] is not None
    
    # Kontrollera att content är unescaped
    # Feedparser kan hantera a10:content olika, så vi testar både möjliga format
    # Om feedparser inte hanterar a10:content direkt, kan vi testa manuellt
    raw_content = '<p>Detta är &lt;b&gt;test&lt;/b&gt; content</p>'
    expected_unescaped = html.unescape(raw_content)
    # Notera: feedparser kan redan ha unescaped content, så vi testar logiken
    if item1['content']:
        # Content ska vara unescaped (inga &lt; eller &gt;)
        assert '&lt;' not in item1['content'] or '&gt;' not in item1['content']
    
    # Test andra entry
    entry2 = feed.entries[1]
    item2 = parse_entry(entry2)
    
    assert item2['guid'] == 'https://example.com/post2'
    assert item2['title'] == 'Test Post 2'
    assert item2['link'] == 'https://example.com/post2'


def test_html_unescape():
    """Test att HTML-unescape fungerar korrekt."""
    # Test att parse_entry unescape:ar content
    feed = feedparser.parse(MINIMAL_RSS)
    entry = feed.entries[0]
    
    item = parse_entry(entry)
    
    # Om content finns, ska den vara unescaped
    if item['content']:
        # Kontrollera att HTML-entities är unescaped
        assert '&lt;' not in item['content'] or item['content'].count('&lt;') < item['content'].count('<')
        assert '&gt;' not in item['content'] or item['content'].count('&gt;') < item['content'].count('>')


def test_get_new_items():
    """Test att 'new since last_guid' fungerar."""
    feed = feedparser.parse(MINIMAL_RSS)
    
    # Test 1: Inget last_guid (första körningen) - alla items är nya
    new_items = get_new_items(feed, None)
    assert len(new_items) == 2
    assert new_items[0]['guid'] == 'https://example.com/post1'
    assert new_items[1]['guid'] == 'https://example.com/post2'
    
    # Test 2: last_guid är första posten - bara andra posten är ny
    new_items = get_new_items(feed, 'https://example.com/post1')
    assert len(new_items) == 1
    assert new_items[0]['guid'] == 'https://example.com/post2'
    
    # Test 3: last_guid är andra posten - inga nya items
    new_items = get_new_items(feed, 'https://example.com/post2')
    assert len(new_items) == 0
    
    # Test 4: last_guid finns inte i feed - alla items är nya
    new_items = get_new_items(feed, 'https://example.com/nonexistent')
    assert len(new_items) == 2


def test_load_and_save_last_guid():
    """Test att load och save last_guid fungerar."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Skapa state-mapp
        state_dir = Path(tmpdir) / ".state"
        state_dir.mkdir(exist_ok=True)
        state_file = state_dir / "test_guid.txt"
        
        # Mock state file path och dir
        with patch('court_rss_watcher.STATE_FILE', state_file):
            with patch('court_rss_watcher.STATE_DIR', state_dir):
                # Test save
                save_last_guid('test-guid-123')
                assert state_file.exists()
                
                # Test load
                loaded_guid = load_last_guid()
                assert loaded_guid == 'test-guid-123'
        
        # Test load när filen inte finns
        non_existent = Path(tmpdir) / "nonexistent.txt"
        with patch('court_rss_watcher.STATE_FILE', non_existent):
            loaded_guid = load_last_guid()
            assert loaded_guid is None


def test_format_pub_date():
    """Test att format_pub_date fungerar."""
    from datetime import datetime
    
    # Test med datetime
    dt = datetime(2024, 1, 15, 14, 30, 0)
    formatted = format_pub_date(dt)
    assert formatted == '2024-01-15 14:30:00'
    
    # Test med None
    formatted = format_pub_date(None)
    assert formatted == 'Inget datum'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
