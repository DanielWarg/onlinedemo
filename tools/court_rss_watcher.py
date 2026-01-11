#!/usr/bin/env python3
"""
RSS-poller för Göteborgs tingsrätt från domstol.se
Hämtar RSS-feed och identifierar nya poster baserat på guid.
"""
import html
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

import feedparser
import requests

# RSS Feed URL
RSS_URL = "https://www.domstol.se/feed/56/?searchPageId=1139&scope=news"

# State file path
STATE_DIR = Path(".state")
STATE_FILE = STATE_DIR / "gbg_tingsratt_last_guid.txt"

# User-Agent for requests
USER_AGENT = "CourtRSSWatcher/1.0 (Python)"
REQUEST_TIMEOUT = 10  # seconds


def ensure_state_dir():
    """Skapa .state-mappen om den inte finns."""
    STATE_DIR.mkdir(exist_ok=True)


def load_last_guid() -> Optional[str]:
    """
    Läs senaste guid från state-fil.
    
    Returns:
        Senaste guid eller None om filen inte finns.
    """
    if not STATE_FILE.exists():
        return None
    
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            guid = f.read().strip()
            return guid if guid else None
    except Exception as e:
        print(f"Fel vid läsning av state-fil: {e}", file=sys.stderr)
        return None


def save_last_guid(guid: str):
    """
    Spara senaste guid till state-fil.
    
    Args:
        guid: GUID att spara.
    """
    try:
        ensure_state_dir()
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            f.write(guid)
    except Exception as e:
        print(f"Fel vid skrivning av state-fil: {e}", file=sys.stderr)


def fetch_rss() -> feedparser.FeedParserDict:
    """
    Hämta RSS-feed från domstol.se.
    
    Returns:
        Parsed feed från feedparser.
    """
    try:
        response = requests.get(
            RSS_URL,
            headers={'User-Agent': USER_AGENT},
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return feedparser.parse(response.content)
    except requests.exceptions.RequestException as e:
        print(f"Fel vid hämtning av RSS: {e}", file=sys.stderr)
        sys.exit(1)


def parse_entry(entry) -> Dict:
    """
    Parse:a en RSS-entry och extrahera relevant data.
    
    Args:
        entry: feedparser entry object.
        
    Returns:
        Dictionary med guid, title, link, pubDate, content.
    """
    # Hämta guid (kan vara i id eller guid-fält)
    guid = getattr(entry, 'id', None) or getattr(entry, 'guid', None) or entry.get('link', '')
    
    # Hämta title
    title = getattr(entry, 'title', '')
    
    # Hämta link
    link = getattr(entry, 'link', '')
    
    # Hämta pubDate (kan vara published eller updated)
    pub_date = None
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        pub_date = datetime(*entry.published_parsed[:6])
    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        pub_date = datetime(*entry.updated_parsed[:6])
    
    # Hämta content från a10:content namespace (HTML-escaped)
    content = ''
    
    # feedparser kan ha content som lista (från content-element)
    if hasattr(entry, 'content'):
        if isinstance(entry.content, list) and len(entry.content) > 0:
            content = entry.content[0].get('value', '')
        elif isinstance(entry.content, str):
            content = entry.content
    
    # Försök hämta från a10:content namespace
    # feedparser kan lägga namespace-attribut i entry eller i entry.get()
    if not content:
        # Försök via getattr (feedparser kan lägga det som attribut)
        content = getattr(entry, 'a10_content', None) or getattr(entry, 'content', None)
    
    # Om fortfarande tomt, försök via dict-get (feedparser kan ha det som dict-nyckel)
    if not content:
        content = entry.get('a10_content', '') or entry.get('content', '')
    
    # Om fortfarande tomt, försök hämta från summary/description som fallback
    if not content:
        content = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
    
    # Unescape HTML-entities
    if content:
        content = html.unescape(content)
    
    return {
        'guid': guid,
        'title': title,
        'link': link,
        'pubDate': pub_date,
        'content': content
    }


def get_new_items(feed: feedparser.FeedParserDict, last_guid: Optional[str]) -> List[Dict]:
    """
    Identifiera nya items sedan senaste guid.
    
    Args:
        feed: Parsed feed från feedparser.
        last_guid: Senaste guid (None om första körningen).
        
    Returns:
        Lista av nya items (Dict med guid, title, link, pubDate, content).
    """
    items = []
    
    # Om inget last_guid, alla items är nya
    if last_guid is None:
        for entry in feed.entries:
            items.append(parse_entry(entry))
        return items
    
    # Sök efter last_guid i feed
    found_last_guid = False
    for entry in feed.entries:
        item = parse_entry(entry)
        
        # Om vi hittat senaste guid, alla efterföljande är nya
        if found_last_guid:
            items.append(item)
        elif item['guid'] == last_guid:
            found_last_guid = True
            # Denna är inte ny, men nästa kommer vara
    
    # Om last_guid inte hittades i feed, behandla alla som nya
    # (kan hända om feed har roterats eller guid har ändrats)
    if not found_last_guid:
        for entry in feed.entries:
            items.append(parse_entry(entry))
    
    return items


def format_pub_date(pub_date: Optional[datetime]) -> str:
    """
    Formatera pubDate för utskrift.
    
    Args:
        pub_date: datetime-objekt eller None.
        
    Returns:
        Formaterad datumsträng.
    """
    if pub_date:
        return pub_date.strftime('%Y-%m-%d %H:%M:%S')
    return 'Inget datum'


def main():
    """Huvudfunktion för RSS-poller."""
    # Läs senaste guid
    last_guid = load_last_guid()
    
    # Hämta RSS-feed
    feed = fetch_rss()
    
    # Kontrollera om feed är tom eller har fel
    if feed.bozo and feed.bozo_exception:
        print(f"Varning: RSS-feed har parsing-fel: {feed.bozo_exception}", file=sys.stderr)
    
    # Identifiera nya items
    new_items = get_new_items(feed, last_guid)
    
    if not new_items:
        print("Inget nytt")
    else:
        # Skriv ut nya poster
        for item in new_items:
            print(f"{format_pub_date(item['pubDate'])} | {item['title']} | {item['link']}")
        
        # Uppdatera state med senaste guid
        if new_items:
            latest_guid = new_items[0]['guid']  # Första item är senaste
            save_last_guid(latest_guid)


if __name__ == "__main__":
    main()
