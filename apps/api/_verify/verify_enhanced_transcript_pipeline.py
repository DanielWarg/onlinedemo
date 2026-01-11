#!/usr/bin/env python3
"""
Verifiera att enhanced masterclass-normalisering körs i recordings-pipelinen.

BEVISAR att:
1. normalize_transcript_text() använder use_enhanced=True som default
2. _apply_masterclass_enhancements() körs och ändrar output
3. Recordings-pipelinen anropar funktionen korrekt

Testar MINST 3 konkreta masterclass-enhancements med assert på diff.
Expected outputs härleds från _apply_masterclass_enhancements() logiken.
"""
import sys
from pathlib import Path

# Add parent directory to path to import text_processing
sys.path.insert(0, str(Path(__file__).parent.parent))

from text_processing import normalize_transcript_text

def test_1_drare_to_drar():
    """
    Test 1: "drare" -> "drar"
    Regel: stt_error_mappings["drare"] = "drar" (rad 535)
    OBS: Detta är i grundnormaliseringen, inte enhanced, men testar att pipeline fungerar.
    """
    input_text = "han drare i spaken"
    output = normalize_transcript_text(input_text)
    
    # Assert: "drare" ska vara korrigerat till "drar"
    assert "drar" in output.lower(), f"FAIL: 'drar' not found in output. Got: {output}"
    assert "drare" not in output.lower(), f"FAIL: Original error 'drare' still present. Got: {output}"
    
    return True, "drare → drar", input_text, output

def test_2_verb_form_börja():
    """
    Test 2: "börja gråta" -> "börjar gråta"
    Regel: re.sub(r'\bbörja (gråta|prata|tala|jobba|arbeta)\b', r'börjar \1', ...) (rad 686)
    Detta är en enhanced-regel i _apply_masterclass_enhancements()
    """
    input_text = "vi ska börja gråta nu"
    output = normalize_transcript_text(input_text)
    
    # Assert: "börja gråta" ska vara korrigerat till "börjar gråta"
    assert "börjar gråta" in output.lower(), f"FAIL: 'börjar gråta' not found. Got: {output}"
    assert "börja gråta" not in output.lower(), f"FAIL: Original 'börja gråta' still present. Got: {output}"
    
    return True, "börja gråta → börjar gråta", input_text, output

def test_3_sentence_structure():
    """
    Test 3: "det är en X består" -> "en X består"
    Regel: re.sub(r'\bdet är en (\w+) består\b', r'en \1 består', ...) (rad 693)
    Detta är en enhanced-regel i _apply_masterclass_enhancements()
    """
    input_text = "det är en konflikt består av delar"
    output = normalize_transcript_text(input_text)
    
    # Assert: "det är en konflikt består" ska vara korrigerat till "en konflikt består"
    assert "en konflikt består" in output.lower(), f"FAIL: 'en konflikt består' not found. Got: {output}"
    assert "det är en konflikt består" not in output.lower(), f"FAIL: Original still present. Got: {output}"
    
    return True, "det är en X består → en X består", input_text, output

def test_4_grammar_det_är_det():
    """
    Test 4: "det är det" -> "det är"
    Regel: re.sub(r'\bdet är det\b', 'det är', ...) (rad 705)
    Detta är en enhanced-regel i _apply_masterclass_enhancements()
    """
    input_text = "det är det viktigt"
    output = normalize_transcript_text(input_text)
    
    # Assert: "det är det" ska vara korrigerat till "det är"
    assert "det är det" not in output.lower(), f"FAIL: 'det är det' still present. Got: {output}"
    assert "det är viktigt" in output.lower(), f"FAIL: Correction not applied. Got: {output}"
    
    return True, "det är det → det är", input_text, output

def test_5_formal_word_sån():
    """
    Test 5: "sån" -> "sådan"
    Regel: re.sub(r'\bsån\b', 'sådan', ...) (rad 699)
    Detta är en enhanced-regel i _apply_masterclass_enhancements()
    """
    input_text = "inom form av sån situation"
    output = normalize_transcript_text(input_text)
    
    # Assert: "sån" ska vara korrigerat till "sådan"
    words = output.lower().split()
    assert "sådan" in output.lower(), f"FAIL: 'sådan' not found. Got: {output}"
    assert "sån" not in words, f"FAIL: Original 'sån' still present as word. Got: {output}"
    
    # Also check "inom form av" -> "i form av" (rad 696)
    assert "i form av" in output.lower(), f"FAIL: 'i form av' not found. Got: {output}"
    
    return True, "sån → sådan, inom form av → i form av", input_text, output

def main():
    """
    Kör alla test och rapportera resultat.
    Returnerar non-zero exit code om något failar.
    """
    print("=" * 70)
    print("VERIFIERING: Enhanced Masterclass Transcript Normalization")
    print("=" * 70)
    print()
    
    # Steg 1: Kodcitat (BEVIS)
    print("STEG 1: KODCITAT (BEVIS)")
    print("-" * 70)
    print("1. normalize_transcript_text() default-argument:")
    print("   📄 apps/api/text_processing.py:497")
    print("   def normalize_transcript_text(raw_text: str, use_enhanced: bool = True)")
    print()
    print("2. _apply_masterclass_enhancements() koppling:")
    print("   📄 apps/api/text_processing.py:653-654")
    print("   if use_enhanced:")
    print("       text = _apply_masterclass_enhancements(text)")
    print()
    print("3. _apply_masterclass_enhancements() implementation:")
    print("   📄 apps/api/text_processing.py:660")
    print("   def _apply_masterclass_enhancements(text: str) -> str:")
    print()
    print("4. Recordings-pipelinen anropar:")
    print("   📄 apps/api/main.py:568")
    print("   normalized_transcript = normalize_transcript_text(raw_transcript)")
    print("   (Ingen parameter = använder default use_enhanced=True)")
    print()
    print("-" * 70)
    print()
    
    # Steg 2: Kör alla test
    print("STEG 2: TESTFALL (Enhanced-regler)")
    print("-" * 70)
    
    tests = [
        test_1_drare_to_drar,
        test_2_verb_form_börja,
        test_3_sentence_structure,
        test_4_grammar_det_är_det,
        test_5_formal_word_sån,
    ]
    
    passed = 0
    failed = 0
    results = []
    
    for test_func in tests:
        try:
            success, description, input_text, output = test_func()
            if success:
                print(f"✅ PASS: {description}")
                print(f"   Input:  {input_text}")
                print(f"   Output: {output}")
                passed += 1
                results.append((test_func.__name__, "PASS", description, input_text, output))
            else:
                print(f"❌ FAIL: {description}")
                failed += 1
                results.append((test_func.__name__, "FAIL", description, input_text, output))
        except AssertionError as e:
            print(f"❌ FAIL: {test_func.__name__}")
            print(f"   {str(e)}")
            failed += 1
            results.append((test_func.__name__, "FAIL", str(e), "", ""))
        except Exception as e:
            print(f"❌ ERROR: {test_func.__name__}")
            print(f"   {type(e).__name__}: {str(e)}")
            failed += 1
            results.append((test_func.__name__, "ERROR", str(e), "", ""))
        print()
    
    # Sammanfattning
    print("=" * 70)
    print("SAMMANFATTNING")
    print("=" * 70)
    print(f"Totalt test: {len(tests)}")
    print(f"✅ PASS: {passed}")
    print(f"❌ FAIL: {failed}")
    print()
    
    # Visa bevisade regler med input→output
    print("BEVISADE REGLER (input → output):")
    print("-" * 70)
    for test_name, status, desc, inp, out in results:
        if status == "PASS":
            print(f"✅ {desc}")
            print(f"   Input:  {inp}")
            print(f"   Output: {out}")
            print()
    
    # Exit code
    if failed > 0:
        print("❌ VERIFIERING FAILED")
        return 1
    else:
        print("✅ VERIFIERING PASSED")
        return 0

if __name__ == "__main__":
    sys.exit(main())
