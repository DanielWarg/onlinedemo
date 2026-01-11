#!/usr/bin/env python3
"""
Omfattande kvalitetstest för transcript enhancement
Testar alla kända Whisper-fel från faktiska transkript
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from text_processing import normalize_transcript_text

# Faktiska fel från våra Whisper-transkript
REAL_ERRORS = {
    "drare": "drar",
    "ytterstaspets": "yttersta spets",
    "funnera": "definierar",
    "höjer östen": "höjer rösten",
    "börja gråta": "börjar gråta",
    "hämrisar": "hänvisar",
    "förypa": "fördjupa",
    "beståndställer": "beståndsdelar",
    "Göteborgens": "Göteborgs",
    "skargång": "jargong",
    "kontors utrimmat": "kontorsutrymme",
    "sjunk-iritationen": "sjönk irritationen",
    "ovena": "ovänner",
}

def test_real_errors():
    """Testa alla kända fel från faktiska transkript"""
    print("=" * 70)
    print("KOMPREHENSIV KVALITETSTEST")
    print("=" * 70)
    print()
    
    all_passed = True
    failed = []
    
    for error, correction in REAL_ERRORS.items():
        # Skapa testmening med felet
        test_input = f"Detta är en test med {error} i texten."
        result = normalize_transcript_text(test_input)
        
        # Kontrollera att felet är fixat
        error_fixed = error.lower() not in result.lower()
        correction_found = correction.lower() in result.lower()
        
        status = "✅ PASS" if (error_fixed and correction_found) else "❌ FAIL"
        if status == "❌ FAIL":
            all_passed = False
            failed.append((error, correction))
        
        print(f"{status} | {error:25} → {correction:25}")
        if not error_fixed:
            print(f"        ⚠️  Felet '{error}' finns kvar i output")
        if not correction_found:
            print(f"        ⚠️  Korrigeringen '{correction}' hittades inte")
    
    print()
    print("=" * 70)
    print("SAMMANFATTNING")
    print("=" * 70)
    print(f"Totalt testade fel: {len(REAL_ERRORS)}")
    print(f"✅ Fixade: {len(REAL_ERRORS) - len(failed)}")
    print(f"❌ Misslyckade: {len(failed)}")
    
    if failed:
        print()
        print("Fel som inte fixades:")
        for error, correction in failed:
            print(f"  - {error} → {correction}")
    
    print()
    print("=" * 70)
    print("FÖRBÄTTRINGSFÖRSLAG")
    print("=" * 70)
    print()
    
    if len(failed) > 0:
        print("⚠️  Ytterligare förbättringar behövs:")
        print("1. Lägg till de misslyckade felkorrigeringarna")
        print("2. Kontrollera regex-mönster för edge cases")
        print("3. Överväg kontextuell korrigering för komplexa fel")
    else:
        print("✅ Alla kända fel fixas korrekt!")
        print()
        print("För ytterligare kvalitetsförbättring, överväg:")
        print("1. Lägg till svenska ordlistor för stavningskontroll")
        print("2. Förbättra grammatikkontroll (verbformer, böjnings)")
        print("3. Kontextuell korrigering (kräver språkmodell)")
        print("4. Meningsstruktur-förbättring")
    
    return all_passed

if __name__ == "__main__":
    success = test_real_errors()
    sys.exit(0 if success else 1)

