#!/usr/bin/env python3
"""
Verification test for transcription quality.

Tests that Whisper produces valid Swedish transcripts:
- Not empty
- At least 10 words
- No stub patterns
- Swedish language heuristic (at least 50% Swedish words)
"""

import sys
import os
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from text_processing import transcribe_audio

# Swedish stopwords for heuristic
SWEDISH_WORDS = {
    'och', 'att', 'det', 'som', 'inte', 'jag', 'vi', 'de', 'är', 'på', 'en', 'ett',
    'för', 'med', 'till', 'av', 'om', 'han', 'hon', 'kan', 'ska', 'var', 'den',
    'har', 'men', 'så', 'här', 'där', 'nu', 'den', 'detta', 'sina', 'sitt',
    'henne', 'honom', 'sina', 'sitt', 'hans', 'hennes', 'deras', 'vår', 'er'
}


def is_swedish_word(word: str) -> bool:
    """Simple heuristic: check if word is Swedish stopword or contains Swedish chars (å, ä, ö)."""
    word_lower = word.lower().strip('.,!?;:"()[]{}')
    if word_lower in SWEDISH_WORDS:
        return True
    # Check for Swedish characters
    if any(char in word_lower for char in ['å', 'ä', 'ö']):
        return True
    return False


def verify_transcription_quality():
    """Run transcription quality verification."""
    
    print("=" * 60)
    print("  TRANSCRIPTION QUALITY VERIFICATION")
    print("=" * 60)
    
    # Find test audio file
    audio_paths = [
        Path(__file__).parent.parent.parent.parent / "Del21.wav",
        Path(__file__).parent / "fixtures" / "test_audio.wav",
        Path("/app/Del21.wav"),
    ]
    
    audio_file = None
    for p in audio_paths:
        if p.exists():
            audio_file = p
            break
    
    if not audio_file:
        print("\n[FAIL] No test audio file found.")
        print("  Please place a Swedish audio file at one of:")
        for p in audio_paths:
            print(f"    - {p}")
        print("  Or create apps/api/_verify/fixtures/test_audio.wav")
        sys.exit(1)
    
    print(f"\n[INFO] Using test audio: {audio_file}")
    
    # Get model name from env
    model_name = os.getenv("WHISPER_MODEL", "base")
    print(f"[INFO] Whisper model: {model_name}")
    
    # Transcribe
    print("\n[INFO] Starting transcription...")
    print("[INFO] Note: large-v3 can take 3-10 minutes for first transcription (model download/load)")
    print("[INFO] Subsequent transcriptions will be faster (model cached)")
    start_time = time.time()
    
    try:
        transcript = transcribe_audio(str(audio_file))
    except KeyboardInterrupt:
        print("\n[FAIL] Transcription interrupted (timeout or user cancel)")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Transcription failed: {type(e).__name__}: {str(e)}")
        sys.exit(1)
    
    elapsed_seconds = time.time() - start_time
    elapsed_ms = int(elapsed_seconds * 1000)
    
    # Extract metadata only (no raw text in output)
    word_count = len(transcript.split())
    char_count = len(transcript)
    
    elapsed_min = int(elapsed_seconds // 60)
    elapsed_sec = int(elapsed_seconds % 60)
    if elapsed_min > 0:
        print(f"[INFO] Transcription completed in {elapsed_min}m {elapsed_sec}s ({elapsed_ms}ms)")
    else:
        print(f"[INFO] Transcription completed in {elapsed_sec}s ({elapsed_ms}ms)")
    print(f"[INFO] Word count: {word_count}, Char count: {char_count}")
    
    # Assertions
    
    # 1. Not empty
    if not transcript or len(transcript.strip()) == 0:
        print("\n[FAIL] Transcript is empty")
        sys.exit(1)
    print("  ✓ Transcript is not empty")
    
    # 2. At least 10 words
    if word_count < 10:
        print(f"\n[FAIL] Transcript too short: {word_count} words (minimum: 10)")
        sys.exit(1)
    print(f"  ✓ Word count OK: {word_count} >= 10")
    
    # 3. No stub patterns
    stub_patterns = [
        "Detta är en inspelning från",
        "Detta är ett röstmemo med",
        "Jag pratar om viktiga saker här"
    ]
    transcript_lower = transcript.lower()
    for pattern in stub_patterns:
        if pattern.lower() in transcript_lower:
            print(f"\n[FAIL] Stub pattern detected: '{pattern}'")
            sys.exit(1)
    print("  ✓ No stub patterns detected")
    
    # 4. Swedish language heuristic (at least 50% Swedish words)
    words = transcript.split()
    swedish_count = sum(1 for word in words if is_swedish_word(word))
    swedish_ratio = swedish_count / len(words) if words else 0
    
    if swedish_ratio < 0.5:
        print(f"\n[FAIL] Swedish ratio too low: {swedish_ratio:.1%} < 50%")
        print(f"  Swedish words: {swedish_count}/{len(words)}")
        sys.exit(1)
    print(f"  ✓ Swedish language: {swedish_count}/{len(words)} words ({swedish_ratio:.1%})")
    
    # Summary
    print("\n" + "=" * 60)
    print("  VERIFICATION PASSED")
    print("=" * 60)
    print(f"  Model: {model_name}")
    print(f"  Words: {word_count}")
    print(f"  Chars: {char_count}")
    print(f"  Elapsed: {elapsed_ms}ms")
    print(f"  Swedish ratio: {swedish_ratio:.1%}")
    print()
    
    sys.exit(0)


if __name__ == "__main__":
    verify_transcription_quality()

