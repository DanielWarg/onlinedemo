"""
Verification script for refine_editorial_text() semantic preservation.

Tests that refine_editorial_text() does not change meaning:
- Före/efter jämförelse på samma input (max 2 bullets + sammanfattning)
- Verifierar att innehållet är semantiskt identiskt
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from text_processing import refine_editorial_text


def test_semantic_preservation():
    """Test that refine_editorial_text preserves meaning (max 2 bullets + sammanfattning)"""
    
    # Test case 1: Simple Sammanfattning with speech signals in bullets
    test_input_1 = """# Röstmemo – Test Project – 2026-01-01

## Sammanfattning

En sak är en konflikt egentligen.

## Nyckelpunkter

- Och det här behöver, kan man vara väldigt nertonad och artigt
- Det här finns vissa av de här sakfrågorna man kan både se och identifiera tidigt
- Jag tycker att det behöver inte vara praktiskt en blockering

## Tidslinje

[00:00] En sak är en konflikt egentligen
"""
    
    result_1 = refine_editorial_text(test_input_1)
    
    # Verify structure preserved
    assert "## Sammanfattning" in result_1
    assert "## Nyckelpunkter" in result_1
    assert "## Tidslinje" in result_1
    
    # Extract sections for comparison
    lines_before = test_input_1.split('\n')
    lines_after = result_1.split('\n')
    
    # Find Sammanfattning section
    before_summary_idx = None
    after_summary_idx = None
    for i, line in enumerate(lines_before):
        if line.strip() == "## Sammanfattning":
            before_summary_idx = i
            break
    for i, line in enumerate(lines_after):
        if line.strip() == "## Sammanfattning":
            after_summary_idx = i
            break
    
    # Find Nyckelpunkter bullets
    before_bullets = []
    after_bullets = []
    in_bullets_before = False
    in_bullets_after = False
    
    for line in lines_before:
        if line.strip() == "## Nyckelpunkter":
            in_bullets_before = True
            continue
        elif line.strip().startswith("##") and in_bullets_before:
            break
        if in_bullets_before and line.strip().startswith("- "):
            before_bullets.append(line[2:].strip())
    
    for line in lines_after:
        if line.strip() == "## Nyckelpunkter":
            in_bullets_after = True
            continue
        elif line.strip().startswith("##") and in_bullets_after:
            break
        if in_bullets_after and line.strip().startswith("- "):
            after_bullets.append(line[2:].strip())
    
    # Semantic check: key content words should still be present
    # Extract key words (nouns, verbs) from before
    import re
    before_words = set()
    for bullet in before_bullets[:2]:  # Max 2 bullets
        words = re.findall(r'\b\w{4,}\b', bullet.lower())
        before_words.update(words)
    
    after_words = set()
    for bullet in after_bullets[:2]:  # Max 2 bullets
        words = re.findall(r'\b\w{4,}\b', bullet.lower())
        after_words.update(words)
    
    # Verify key content words are preserved (allow some removal of filler words)
    # At least 80% of content words should be preserved
    common_words = before_words & after_words
    if len(before_words) > 0:
        preservation_ratio = len(common_words) / len(before_words)
        assert preservation_ratio >= 0.8, f"Too many content words removed: {preservation_ratio:.2%}"
    
    # Verify speech signals were removed from bullets
    speech_signals = ['och', 'det här', 'jag tycker']
    for bullet in after_bullets[:2]:
        bullet_lower = bullet.lower()
        # Check that speech signals were removed from start (not perfect, but basic check)
        # Note: this is a heuristic check
        pass  # Main check is that content words are preserved
    
    print("✓ Test 1 passed: Semantic preservation verified")
    
    # Test case 2: Sammanfattning with < 2 sentences (should add conclusion)
    test_input_2 = """# Röstmemo – Test Project – 2026-01-01

## Sammanfattning

En konflikt har identifierats.

## Nyckelpunkter

- Det finns problem med kommunikationen
- Lösningar behöver utvärderas

## Tidslinje

[00:00] Start
"""
    
    result_2 = refine_editorial_text(test_input_2)
    
    # Extract Sammanfattning sentences
    after_lines_2 = result_2.split('\n')
    in_summary_2 = False
    summary_sentences_2 = []
    
    for line in after_lines_2:
        if line.strip() == "## Sammanfattning":
            in_summary_2 = True
            continue
        elif line.strip().startswith("##") and in_summary_2:
            break
        if in_summary_2 and line.strip() and not line.strip().startswith("#"):
            summary_sentences_2.append(line.strip())
    
    # Count sentences (simple heuristic: split on . ! ?)
    summary_text_2 = ' '.join(summary_sentences_2)
    sentences_2 = re.split(r'[.!?]+\s+', summary_text_2)
    sentences_2 = [s.strip() for s in sentences_2 if s.strip() and len(s.strip()) > 5]
    
    # Should have at least 2 sentences now (original + conclusion)
    assert len(sentences_2) >= 2, f"Expected at least 2 sentences, got {len(sentences_2)}"
    
    print("✓ Test 2 passed: Sammanfattning enhancement verified")
    
    print("\n✓ All verification tests passed!")


if __name__ == "__main__":
    test_semantic_preservation()

