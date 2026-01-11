"""
Scout RSS feed fetching logic.
"""
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

import feedparser
import requests

from models import ScoutFeed, ScoutItem

logger = logging.getLogger(__name__)

# User-Agent for RSS requests
USER_AGENT = "Scout/1.0 (journalist workspace)"
REQUEST_TIMEOUT = 10  # seconds


def calculate_guid_hash(feed_url: str, entry: Dict) -> str:
    """
    Calculate unique hash for RSS item deduplication.
    
    Args:
        feed_url: URL of the feed
        entry: Dictionary with entry data (id, link, title, published, updated)
        
    Returns:
        SHA256 hash as hex string
    """
    stable_id = (
        entry.get('id') or 
        entry.get('link') or 
        (entry.get('title', '') + str(entry.get('published') or entry.get('updated') or ''))
    )
    hash_input = f"{feed_url}{stable_id}"
    return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()


def parse_rss_feed(url: str, content: Optional[bytes] = None) -> List[Dict]:
    """
    Parse RSS/Atom feed using feedparser.
    
    Args:
        url: Feed URL
        
    Returns:
        List of entry dictionaries with keys: title, link, published_parsed, updated_parsed, id
    """
    entries = []
    
    try:
        # Parse från redan hämtad respons om möjligt (undvik dubbel-fetch utan headers)
        feed = feedparser.parse(content if content is not None else url)
        
        for entry in feed.entries:
            entries.append({
                'title': getattr(entry, 'title', ''),
                'link': getattr(entry, 'link', ''),
                'published_parsed': getattr(entry, 'published_parsed', None),
                'updated_parsed': getattr(entry, 'updated_parsed', None),
                'id': getattr(entry, 'id', getattr(entry, 'link', ''))
            })
    except Exception as e:
        logger.warning(f"Failed to parse feed {url}: {e}")
        return []
    
    return entries


def fetch_all_feeds(db: Session) -> Dict[int, int]:
    """
    Fetch all enabled feeds and save new items.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary mapping feed_id to count of new items created
    """
    feeds = db.query(ScoutFeed).filter(ScoutFeed.is_enabled.is_(True)).all()
    results = {}
    
    for feed in feeds:
        try:
            # Skip feeds with empty URL
            if not feed.url:
                logger.warning(f"Scout feed {feed.id} ({feed.name}): empty URL, skipping")
                results[feed.id] = 0
                continue
            
            # Fetch feed with timeout and User-Agent
            try:
                response = requests.get(
                    feed.url,
                    timeout=REQUEST_TIMEOUT,
                    headers={'User-Agent': USER_AGENT}
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                # Log metadata only (no content)
                logger.error(f"Scout feed {feed.id} ({feed.name}): HTTP error - {type(e).__name__}")
                db.rollback()
                results[feed.id] = 0
                continue
            
            # Parse feed (använd response.content så vi inte gör en ny fetch i feedparser)
            entries = parse_rss_feed(feed.url, content=response.content)
            
            if not entries:
                logger.warning(f"Scout feed {feed.id} ({feed.name}): no entries found")
                results[feed.id] = 0
                continue
            
            new_count = 0
            
            for entry in entries:
                # Calculate dedup hash
                guid_hash = calculate_guid_hash(feed.url, entry)
                
                # Check if item already exists
                existing = db.query(ScoutItem).filter(ScoutItem.guid_hash == guid_hash).first()
                if existing:
                    continue
                
                # Parse published date from feedparser time tuple
                published_at = None
                if entry.get('published_parsed'):
                    try:
                        published_at = datetime.fromtimestamp(
                            time.mktime(entry['published_parsed']),
                            tz=timezone.utc
                        )
                    except Exception:
                        pass
                
                # Fallback to updated_parsed if published_parsed not available
                if not published_at and entry.get('updated_parsed'):
                    try:
                        published_at = datetime.fromtimestamp(
                            time.mktime(entry['updated_parsed']),
                            tz=timezone.utc
                        )
                    except Exception:
                        pass
                
                # Create new item
                item = ScoutItem(
                    feed_id=feed.id,
                    title=entry.get('title', '')[:500],  # Limit length
                    link=entry.get('link', '')[:1000],  # Limit length
                    published_at=published_at,
                    guid_hash=guid_hash,
                    raw_source=feed.name
                )
                db.add(item)
                new_count += 1
            
            db.commit()
            results[feed.id] = new_count
            
            # Log metadata only (no content)
            logger.info(f"Scout feed {feed.id} ({feed.name}): {new_count} nya items")
            
        except Exception as e:
            # Fail-closed: log error but don't crash
            logger.error(f"Scout feed {feed.id} ({feed.name}): fetch failed - {type(e).__name__}: {str(e)}")
            db.rollback()
            results[feed.id] = 0
    
    return results
