"""
Feed fetching and parsing with robust SSRF protection.
"""
import html
import ipaddress
import logging
import re
import socket
from typing import Dict, List, Tuple
from urllib.parse import urlparse, urljoin

import feedparser
import requests

# Fulltext extraction dependencies (optional imports)
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    import html2text
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

logger = logging.getLogger(__name__)

# Constants
REQUEST_TIMEOUT = 10  # seconds
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB
USER_AGENT = "Arbetsytan/1.0 (feed import)"
MAX_REDIRECTS = 5


def _is_private_ip(ip: str) -> bool:
    """
    Check if IP address is private/localhost/link-local.
    
    Args:
        ip: IP address string
        
    Returns:
        True if IP is private/localhost/link-local
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        return (
            ip_obj.is_private or
            ip_obj.is_loopback or
            ip_obj.is_link_local or
            ip_obj.is_reserved or
            ip == "0.0.0.0"
        )
    except ValueError:
        return True  # Invalid IP is treated as blocked


def _resolve_and_validate_host(hostname: str) -> bool:
    """
    Resolve hostname to IP and validate it's not private.
    
    Args:
        hostname: Hostname to resolve
        
    Returns:
        True if hostname resolves to public IP, False if private/blocked
        
    Raises:
        ValueError: If hostname cannot be resolved
    """
    try:
        # Resolve to IP
        ip = socket.gethostbyname(hostname)
        if _is_private_ip(ip):
            logger.warning(f"Blocked private IP after DNS resolution: {hostname} -> {ip}")
            return False
        return True
    except socket.gaierror as e:
        raise ValueError(f"Failed to resolve hostname {hostname}: {e}")


def _validate_url_scheme(url: str) -> bool:
    """
    Validate URL scheme is http or https.
    
    Args:
        url: URL to validate
        
    Returns:
        True if scheme is http/https, False otherwise
    """
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https')


def validate_and_fetch(
    url: str,
    timeout: int = REQUEST_TIMEOUT,
    max_bytes: int = MAX_RESPONSE_SIZE,
) -> Tuple[bytes, str]:
    """
    Fetch URL with robust SSRF protection, return content and content-type.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        max_bytes: Maximum response size in bytes
        
    Returns:
        Tuple of (content_bytes, content_type_header)
        
    Raises:
        ValueError: If URL is invalid, blocked, or fetch fails
        requests.exceptions.RequestException: If network request fails
    """
    # Use existing validate_and_fetch logic but return content-type too
    # Validate scheme
    if not _validate_url_scheme(url):
        raise ValueError(f"Invalid URL scheme. Only http:// and https:// are allowed. Got: {urlparse(url).scheme}")
    
    parsed = urlparse(url)
    
    # Block localhost/private hostnames
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL missing hostname")
    
    # Block obvious localhost patterns
    if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1', '[::1]'):
        raise ValueError(f"Blocked localhost hostname: {hostname}")
    
    # Resolve and validate hostname (DNS + IP check)
    if not _resolve_and_validate_host(hostname):
        raise ValueError(f"Blocked private IP for hostname: {hostname}")
    
    # Fetch with redirect handling and validation
    session = requests.Session()
    current_url = url
    redirects_followed = 0
    MAX_REDIRECTS_LOCAL = 3  # Max 3 redirects for article fetching
    
    try:
        while redirects_followed <= MAX_REDIRECTS_LOCAL:
            response = session.get(
                current_url,
                timeout=timeout,
                headers={'User-Agent': USER_AGENT},
                allow_redirects=False,
                stream=True
            )
            
            # Validate current URL hostname
            current_parsed = urlparse(current_url)
            current_hostname = current_parsed.hostname
            if current_hostname and not _resolve_and_validate_host(current_hostname):
                raise ValueError(f"Blocked private IP: {current_hostname}")
            
            # Check for redirect
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get('Location')
                if not redirect_url:
                    raise ValueError("Redirect response missing Location header")
                
                redirect_url = urljoin(current_url, redirect_url)
                redirect_parsed = urlparse(redirect_url)
                if redirect_parsed.scheme not in ("http", "https"):
                    raise ValueError(f"Invalid redirect scheme: {redirect_parsed.scheme}")
                
                redirect_hostname = redirect_parsed.hostname
                if redirect_hostname and not _resolve_and_validate_host(redirect_hostname):
                    raise ValueError(f"Blocked private IP in redirect: {redirect_hostname}")
                
                current_url = redirect_url
                redirects_followed += 1
                continue
            
            break
        
        if redirects_followed > MAX_REDIRECTS_LOCAL:
            raise ValueError(f"Too many redirects (max {MAX_REDIRECTS_LOCAL})")
        
        response.raise_for_status()
        
        # Final validation
        final_parsed = urlparse(response.url)
        final_hostname = final_parsed.hostname
        if final_hostname and not _resolve_and_validate_host(final_hostname):
            raise ValueError(f"Blocked private IP in final URL: {final_hostname}")
        
        # Check content length
        content_length = response.headers.get('Content-Length')
        if content_length:
            size = int(content_length)
            if size > max_bytes:
                raise ValueError(f"Response too large: {size} bytes (max {max_bytes})")
        
        # Read response with size limit
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_bytes:
                raise ValueError(f"Response exceeds size limit: {max_bytes} bytes")
        
        content_type = response.headers.get('Content-Type', '')
        return (content, content_type)
        
    except requests.exceptions.Timeout:
        raise ValueError(f"Request timeout after {timeout}s")
    except requests.exceptions.TooManyRedirects:
        raise ValueError(f"Too many redirects (max {MAX_REDIRECTS_LOCAL})")
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to fetch URL: {str(e)}")


def fetch_feed_url(url: str) -> bytes:
    """
    Fetch feed URL (wrapper for validate_and_fetch, returns bytes only).
    
    Args:
        url: Feed URL to fetch
        
    Returns:
        Feed content as bytes
    """
    content, _ = validate_and_fetch(url)
    return content


def fetch_article_text(url: str) -> str:
    """
    Fetch article URL and extract main text content.
    
    Uses trafilatura primarily, falls back to BeautifulSoup + html2text.
    
    Args:
        url: Article URL to fetch
        
    Returns:
        Clean plaintext (empty string if extraction fails)
    """
    try:
        content_bytes, content_type = validate_and_fetch(url, timeout=10, max_bytes=5*1024*1024)
        html_content = content_bytes.decode('utf-8', errors='ignore')
        
        # Primary: trafilatura
        if TRAFILATURA_AVAILABLE:
            try:
                extracted = trafilatura.extract(
                    html_content,
                    include_comments=False,
                    include_tables=False,
                    include_images=False
                )
                if extracted and extracted.strip():
                    # Clean and normalize whitespace
                    text = re.sub(r'\s+', ' ', extracted)
                    return text.strip()
            except Exception as e:
                logger.warning(f"Trafilatura extraction failed for {url}: {e}")
        
        # Fallback: BeautifulSoup + html2text
        if BS4_AVAILABLE:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "header", "footer"]):
                    script.decompose()
                
                # Try to find main content (article tag or main tag)
                article = soup.find('article') or soup.find('main') or soup.find('body')
                if article:
                    # Use html2text for clean conversion
                    h = html2text.HTML2Text()
                    h.ignore_links = False
                    h.ignore_images = True
                    text = h.handle(str(article))
                    # Clean whitespace
                    text = re.sub(r'\s+', ' ', text)
                    return text.strip()
            except Exception as e:
                logger.warning(f"BeautifulSoup extraction failed for {url}: {e}")
        
        # Last resort: simple text extraction
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
        
    except Exception as e:
        logger.error(f"Failed to fetch article text from {url}: {e}")
        return ""


def derive_tags(feed_title: str, feed_url: str) -> List[str]:
    """
    Derive tags from feed title and URL.
    
    Always includes "rss".
    If "polisen" in title/URL: includes "polisen".
    Extracts region from feed_title (split on " – " or " - ") and slugs it.
    
    Args:
        feed_title: Feed title
        feed_url: Feed URL
        
    Returns:
        List of tag strings (no duplicates, stable order)
    """
    tags = ["rss"]
    
    # Check for "polisen"
    title_lower = feed_title.lower()
    url_lower = feed_url.lower()
    if "polisen" in title_lower or "polisen" in url_lower:
        tags.append("polisen")
    
    # Extract region from feed_title
    # Split on " – " (em dash) or " - " (hyphen)
    parts = re.split(r'\s*[–-]\s*', feed_title, maxsplit=1)
    if len(parts) > 1:
        region_raw = parts[1].strip()
        if region_raw:
            # Slug: lowercase, replace spaces with hyphens, keep unicode
            region_slug = re.sub(r'\s+', '-', region_raw.lower())
            # Remove any remaining special chars except hyphens
            region_slug = re.sub(r'[^\w\-åäöÅÄÖ]', '', region_slug)
            if region_slug and region_slug != "rss":
                tags.append(region_slug)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    
    return unique_tags


def html_to_text(html_content: str) -> str:
    """
    Convert HTML content to plain text by stripping tags.
    
    Args:
        html_content: HTML string
        
    Returns:
        Plain text with HTML tags removed
    """
    if not html_content:
        return ""
    
    # Unescape HTML entities first
    text = html.unescape(html_content)
    
    # Simple HTML tag removal (regex-based, safe for feed summaries)
    import re
    # Remove script and style tags and their content
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text


def parse_feed(content: bytes) -> Dict:
    """
    Parse RSS/Atom feed using feedparser.
    
    Args:
        content: Feed content as bytes
        
    Returns:
        Dictionary with:
        - title: str
        - description: str (optional)
        - items: List[Dict] with guid, title, link, published, summary_text
    """
    try:
        # feedparser can parse bytes directly
        feed = feedparser.parse(content)
        
        if feed.bozo and feed.bozo_exception:
            logger.warning(f"Feed parsing warning: {feed.bozo_exception}")
        
        # Extract feed metadata
        feed_title = getattr(feed.feed, 'title', 'Untitled Feed')
        feed_description = getattr(feed.feed, 'description', '')
        
        # Extract items
        items = []
        for entry in feed.entries:
            # Get guid (prioritize id, then guid, then link)
            guid = getattr(entry, 'id', None) or getattr(entry, 'guid', None)
            if not guid:
                guid = getattr(entry, 'link', '')
            
            # Get title
            title = getattr(entry, 'title', '')
            
            # Get link
            link = getattr(entry, 'link', '')
            
            # Get published date
            published = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                from datetime import datetime
                published = datetime(*entry.published_parsed[:6]).isoformat()
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                from datetime import datetime
                published = datetime(*entry.updated_parsed[:6]).isoformat()
            
            # Get summary/content and convert HTML to text
            summary_html = ''
            if hasattr(entry, 'summary'):
                summary_html = entry.summary
            elif hasattr(entry, 'content'):
                if isinstance(entry.content, list) and len(entry.content) > 0:
                    summary_html = entry.content[0].get('value', '')
                elif isinstance(entry.content, str):
                    summary_html = entry.content
            
            summary_text = html_to_text(summary_html) if summary_html else ''
            
            items.append({
                'guid': guid,
                'title': title,
                'link': link,
                'published': published,
                'summary_text': summary_text
            })
        
        return {
            'title': feed_title,
            'description': feed_description,
            'items': items
        }
        
    except Exception as e:
        raise ValueError(f"Failed to parse feed: {str(e)}")
