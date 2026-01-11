#!/usr/bin/env python3
"""Temporary script to test transcription with large-v3."""
import sys
import os
import time
sys.path.insert(0, '/app')

from text_processing import transcribe_audio

print('=' * 60)
print('Transkribering av Del21.wav med Whisper large-v3')
print('=' * 60)
print('WHISPER_MODEL:', os.getenv('WHISPER_MODEL', 'NOT SET'))
print()

start = time.time()
try:
    transcript = transcribe_audio('/app/Del21.wav')
    elapsed = time.time() - start
    
    print(f'Tid: {elapsed:.1f} sekunder')
    print(f'Längd: {len(transcript)} tecken, {len(transcript.split())} ord')
    print()
    print('=' * 60)
    print('TRANSCRIPT (första 800 tecken):')
    print('=' * 60)
    print(transcript[:800])
    print('...')
    print('=' * 60)
    print('TRANSCRIPT (sista 800 tecken):')
    print('=' * 60)
    print(transcript[-800:])
    print('=' * 60)
except Exception as e:
    print(f'Fel: {type(e).__name__}: {str(e)[:200]}')
    import traceback
    traceback.print_exc()

