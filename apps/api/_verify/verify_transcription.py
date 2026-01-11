#!/usr/bin/env python3
"""
Verify that audio transcription produces real transcripts (not stub).

This script:
1. Transcribes a test audio file
2. Asserts transcript is not stub (contains more than X words, doesn't contain stub patterns)
3. Exits with code 0 if verification passes, 1 if it fails.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import text_processing
sys.path.insert(0, str(Path(__file__).parent.parent))

from text_processing import transcribe_audio

def verify_transcription(audio_path: str) -> bool:
    """
    Verify transcription produces real content (not stub).
    
    Returns True if verification passes, False otherwise.
    """
    try:
        # Transcribe audio
        transcript = transcribe_audio(audio_path)
        
        # Assert transcript is not empty
        if not transcript or len(transcript.strip()) < 10:
            print(f"FAIL: Transcript is empty or too short: {len(transcript)} chars")
            return False
        
        # Assert transcript has sufficient words (at least 5 words)
        words = transcript.split()
        if len(words) < 5:
            print(f"FAIL: Transcript has too few words: {len(words)} (expected >= 5)")
            return False
        
        # Assert transcript doesn't contain stub patterns
        stub_patterns = [
            "Detta är en inspelning från",
            "Detta är ett röstmemo med",
            "Jag pratar om viktiga saker här"
        ]
        for pattern in stub_patterns:
            if pattern in transcript:
                print(f"FAIL: Transcript contains stub pattern: {pattern}")
                return False
        
        # Success
        print(f"✓ Transcript verified: {len(words)} words, {len(transcript)} chars")
        print(f"✓ First 100 chars: {transcript[:100]}...")
        return True
        
    except Exception as e:
        print(f"FAIL: Transcription error: {str(e)}")
        return False


def main():
    """Main verification function."""
    if len(sys.argv) < 2:
        print("Usage: python verify_transcription.py <audio_file_path>")
        print("Example: python verify_transcription.py test_audio.webm")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    if not os.path.exists(audio_path):
        print(f"FAIL: Audio file not found: {audio_path}")
        sys.exit(1)
    
    success = verify_transcription(audio_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

