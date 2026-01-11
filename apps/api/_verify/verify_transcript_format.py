#!/usr/bin/env python3
"""
Verification script for process_transcript() markdown format.
Tests that output has correct structure without requiring frontend or project settings.
"""
import sys
import os

# Add parent directory to path to import text_processing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from text_processing import process_transcript

def test_transcript_format():
    """Test that process_transcript produces correct markdown format"""
    # Test input
    raw_transcript = "Detta är en test. Jag pratar om viktiga saker här. Detta är en längre mening som innehåller mer information om ämnet och problemet vi diskuterar. Vi behöver tänka på nästa steg och vad som krävs för att lösa detta. Det finns en deadline som måste hållas och källor som behöver verifieras. Detta är en risk som vi måste ta hänsyn till i vårt arbete. Ytterligare detaljer kommer här som är relevanta för projektet. Slutligen avslutar jag med några sista tankar om vad som behöver göras härnäst."
    project_name = "Test Project"
    recording_date = "2025-12-31"
    
    # Process transcript
    result = process_transcript(raw_transcript, project_name, recording_date, duration_seconds=120)
    
    # Assertions
    errors = []
    
    # Check for title
    if "# Röstmemo –" not in result:
        errors.append("Missing title with '# Röstmemo –'")
    
    # Check for correct section separators
    if "\n\n## Sammanfattning\n\n" not in result:
        errors.append("Missing '\\n\\n## Sammanfattning\\n\\n' pattern")
    
    if "\n\n## Nyckelpunkter\n\n" not in result:
        errors.append("Missing '\\n\\n## Nyckelpunkter\\n\\n' pattern")
    
    if "\n\n## Tidslinje\n\n" not in result:
        errors.append("Missing '\\n\\n## Tidslinje\\n\\n' pattern")
    
    # Check for bullets
    if "\n- " not in result:
        errors.append("Missing bullet points starting with '\\n- '")
    
    # Check for timeline entries
    if "\n[00:" not in result:
        errors.append("Missing timeline entries starting with '\\n[00:'")
    
    # Check no trailing whitespace
    for line in result.split('\n'):
        if line != line.rstrip():
            errors.append(f"Line has trailing whitespace: '{line}'")
            break
    
    if errors:
        print("❌ Verification FAILED:")
        for error in errors:
            print(f"  - {error}")
        print("\nOutput preview (first 30 lines):")
        print("\n".join(result.split('\n')[:30]))
        return False
    else:
        print("✓ Verification PASSED")
        print("\nOutput structure verified:")
        print("  ✓ Title present")
        print("  ✓ Section separators correct (\\n\\n before/after headings)")
        print("  ✓ Bullets present")
        print("  ✓ Timeline entries present")
        print("  ✓ No trailing whitespace")
        return True

if __name__ == "__main__":
    success = test_transcript_format()
    sys.exit(0 if success else 1)

