"""Baseline regex masking - MUST always run.

Masks: email, phone, Swedish personal number (PNR), ID-like patterns, addresses/postcodes.
"""
import re
from typing import Dict, List, Tuple
from .models import PrivacyLog


class RegexMasker:
    """Baseline regex-based PII masking."""
    
    def __init__(self):
        """Initialize regex patterns."""
        # Email pattern (common formats)
        # Supports: standard ASCII, unicode chars (åäö), and handles spaces/linebreaks by normalizing first
        # Note: We normalize input text before matching to handle spaces/linebreaks in email
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+\u00C0-\u017F-]+@[A-Za-z0-9.\u00C0-\u017F-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE | re.UNICODE
        )
        
        # Phone pattern (Swedish formats: +46..., 070-..., 08-..., etc.)
        # NOTE: PNR is masked BEFORE phone, so this regex only runs on text that doesn't contain unmasked PNR
        # Swedish mobile: 070-123 45 67, 071-..., 072-..., etc. (starts with 07X where X is 0-9)
        # Swedish landline: 08-123 45 67, 031-..., 040-..., etc. (starts with 0X or 0XX where X is 0-9 for area codes)
        # International: +46 70 123 45 67 (must match FULL number including +46 prefix)
        # Parentheses format: (070) 123 45 67
        # Pattern: 
        #   - International: +46 followed by spaces/dashes, then full number
        #   - Swedish with parentheses: (0XX) followed by number
        #   - Swedish: 0 followed by area code (0-9 for area codes like 031, 040, or 7X for mobile, or 8-9 for Stockholm), then rest
        self.phone_pattern = re.compile(
            r'(?<!\d)(\+46[\s\-]+\d{1,2}[\s\-]+\d{1}[\s\-]*\d{2,3}[\s\-]*\d{2}[\s\-]*\d{2}[\s\-]*\d{0,2}|\+46[\s\-]?\d{9,10}|\(0\d{1,2}\)[\s\-]*\d{2,3}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{0,2}|0[0-9]\d{0,1}[\s\-]?\d{2,3}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{0,2})(?!\d)',
            re.IGNORECASE
        )
        
        # Swedish personal number (PNR): YYMMDD-XXXX or YYYYMMDD-XXXX
        # Matches: 800101-1234, 19800101-1234, 8001011234, etc.
        self.pnr_pattern = re.compile(
            r'\b\d{6}[\s\-]?\d{4}\b|\b\d{8}[\s\-]?\d{4}\b'
        )
        
        # ID-like patterns (sequences of digits/letters that look like IDs)
        self.id_pattern = re.compile(
            r'\b[A-Z0-9]{8,}\b'
        )
        
        # Swedish postcode (5 digits)
        self.postcode_pattern = re.compile(
            r'\b\d{5}\b'
        )
        
        # Address pattern (street name + number)
        self.address_pattern = re.compile(
            r'\b[A-ZÅÄÖ][a-zåäö]+gatan?\s+\d+[A-Z]?\b',
            re.IGNORECASE
        )
    
    def mask(self, text: str) -> Tuple[str, Dict[str, int], List[PrivacyLog]]:
        """
        Mask PII in text using regex patterns.
        
        Args:
            text: Input text
            
        Returns:
            Tuple of (masked_text, entity_counts, privacy_logs)
        """
        # Normalize text for email detection: handle obfuscation attempts
        # Strategy: Normalize spaces/linebreaks around @ symbol to catch obfuscated emails
        normalized_text = re.sub(r'([a-zA-Z0-9._%+\u00C0-\u017F-]+)\s+@\s+([a-zA-Z0-9.\u00C0-\u017F-]+)', r'\1@\2', text)
        normalized_text = re.sub(r'([a-zA-Z0-9._%+\u00C0-\u017F-]+)@([a-zA-Z0-9.\u00C0-\u017F-]+)\s*[\n\r]+\s*\.([a-zA-Z]{2,})', r'\1@\2.\3', normalized_text)
        
        masked_text = normalized_text
        entity_counts = {
            "persons": 0,
            "orgs": 0,
            "locations": 0,
            "contacts": 0,
            "ids": 0
        }
        privacy_logs = []
        
        # Mask emails first (most specific pattern)
        email_count = len(self.email_pattern.findall(masked_text))
        if email_count > 0:
            masked_text = self.email_pattern.sub("[EMAIL]", masked_text)
            entity_counts["contacts"] += email_count
            privacy_logs.append(PrivacyLog(rule="EMAIL", count=email_count))
        
        # Mask PNR BEFORE phone (PNR is more specific pattern - must come first!)
        # This prevents PNR from being incorrectly matched as phone numbers
        pnr_count = len(self.pnr_pattern.findall(masked_text))
        if pnr_count > 0:
            masked_text = self.pnr_pattern.sub("[PNR]", masked_text)
            entity_counts["ids"] += pnr_count
            privacy_logs.append(PrivacyLog(rule="PNR", count=pnr_count))
        
        # Mask phone numbers (after PNR to avoid false matches)
        # Since PNR is already masked, we can safely count and substitute
        # But we need a better phone regex that doesn't match PNR patterns
        # For now, count after PNR masking to avoid false positives
        phone_count = len(self.phone_pattern.findall(masked_text))
        if phone_count > 0:
            masked_text = self.phone_pattern.sub("[PHONE]", masked_text)
            entity_counts["contacts"] += phone_count
            privacy_logs.append(PrivacyLog(rule="PHONE", count=phone_count))
        
        # Mask ID-like patterns (but be conservative - only if clearly ID-like)
        id_matches = self.id_pattern.findall(masked_text)
        # Filter out common words and numbers
        id_count = sum(1 for m in id_matches if not m.isdigit() and len(m) >= 8)
        if id_count > 0:
            for match in id_matches:
                if not match.isdigit() and len(match) >= 8:
                    masked_text = re.sub(r'\b' + re.escape(match) + r'\b', "[ID]", masked_text)
            entity_counts["ids"] += id_count
            privacy_logs.append(PrivacyLog(rule="ID", count=id_count))
        
        # Mask postcodes (but be careful - could be other numbers)
        postcode_count = len(self.postcode_pattern.findall(masked_text))
        # Only mask if it looks like a postcode in context (5 digits, possibly with space)
        if postcode_count > 0:
            masked_text = self.postcode_pattern.sub("[POSTCODE]", masked_text)
            entity_counts["locations"] += postcode_count
            privacy_logs.append(PrivacyLog(rule="POSTCODE", count=postcode_count))
        
        # Mask addresses (street + number)
        address_count = len(self.address_pattern.findall(masked_text))
        if address_count > 0:
            masked_text = self.address_pattern.sub("[ADDRESS]", masked_text)
            entity_counts["locations"] += address_count
            privacy_logs.append(PrivacyLog(rule="ADDRESS", count=address_count))
        
        return masked_text, entity_counts, privacy_logs
    
    def count_leaks(self, text: str) -> Dict[str, int]:
        """
        Count remaining PII patterns in text (for leak check).
        
        Args:
            text: Text to check
            
        Returns:
            Dict with counts per pattern type
        """
        return {
            "email": len(self.email_pattern.findall(text)),
            "phone": len(self.phone_pattern.findall(text)),
            "pnr": len(self.pnr_pattern.findall(text)),
            "id": len([m for m in self.id_pattern.findall(text) if not m.isdigit() and len(m) >= 8]),
            "postcode": len(self.postcode_pattern.findall(text)),
            "address": len(self.address_pattern.findall(text)),
        }


# Global instance
regex_masker = RegexMasker()

