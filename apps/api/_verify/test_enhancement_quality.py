#!/usr/bin/env python3
"""
Test transcript enhancement quality med faktiska Whisper-fel
Från våra tidigare transkript (base och medium)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from text_processing import normalize_transcript_text

# Faktiska exempel från Whisper-transkript med kända fel
test_cases = [
    {
        "name": "Base-modell fel",
        "input": "Om vi drare till sin ytterstaspets så ser vi att i världen har det funnits väldigt stora våldsamma konflikter. Det funnera vi en konflikt som någon form av oenighet. Vad är destruktiva beteenden? Du ska inte bara tänka på de här konflikterna. Den så kallade varma konflikterna. Där kanske man kan se att människor blir upprörda, de höjer östen, vissa kanske börja gråta.",
        "expected_fixes": [
            "drare" not in "output",  # Ska vara "drar"
            "ytterstaspets" not in "output",  # Ska vara "yttersta spets"
            "funnera" not in "output",  # Ska vara "definierar"
            "höjer östen" not in "output",  # Ska vara "höjer rösten"
            "börja gråta" not in "output",  # Ska vara "börjar gråta"
        ]
    },
    {
        "name": "Medium-modell fel",
        "input": "en sak. Vad är en konflikt egentligen? Där finns det ju hur många olika definitioner som helst. Det finns ju också hur många olika storlekar som helst på konflikter. Om vi drar det till sin yttersta spets så ser vi ju då att i världen så har det funnits väldigt stora, våldsamma konflikter.",
        "expected_fixes": [
            "en sak." in "output",  # Börjar med liten bokstav - ska fixas
        ]
    },
    {
        "name": "Vanliga STT-artefakter",
        "input": "Det här är det det det en test. och och och vi behöver se om det fungerar. det är det det är det viktigt.",
        "expected_fixes": [
            "det det det" not in "output",  # Ska tas bort
            "och och och" not in "output",  # Ska tas bort
            "det är det det är det" not in "output",  # Ska fixas
        ]
    },
    {
        "name": "Interpunktion och kapitalisering",
        "input": "detta är en mening. detta är en annan mening. detta är en tredje mening.",
        "expected_fixes": [
            "Detta" in "output",  # Första ordet ska vara stort
            ". Detta" in "output",  # Efter punkt ska vara stort
        ]
    },
    {
        "name": "Komplexa fel från faktiska transkript",
        "input": "Det jag kommer berätta nu, det hämrisar jag till Thomas Jordan på Göteborgens universitet. För de som vill förypa sig ytterligare i hans forskning finns det utbildningar annat att tillgå. Han pratar i alla fall om att en konflikt har fyra beståndställer.",
        "expected_fixes": [
            "hämrisar" not in "output",  # Ska vara "hänvisar"
            "Göteborgens" not in "output",  # Ska vara "Göteborgs"
            "förypa" not in "output",  # Ska vara "fördjupa"
            "beståndställer" not in "output",  # Ska vara "beståndsdelar"
        ]
    },
]

def test_enhancement():
    print("=" * 70)
    print("TEST: Transcript Enhancement Quality")
    print("=" * 70)
    print()
    
    total_tests = 0
    
    for test_case in test_cases:
        print(f"📝 Test: {test_case['name']}")
        print(f"   Input: {test_case['input'][:80]}...")
        
        output = normalize_transcript_text(test_case['input'])
        
        print(f"   Output: {output[:80]}...")
        
        # Kontrollera förväntade fixar
        for i, expected in enumerate(test_case.get('expected_fixes', [])):
            total_tests += 1
            # Här skulle vi kunna göra mer avancerad kontroll
            # För nu kollar vi visuellt
        
        print()
    
    # Ytterligare kvalitetskontroller
    print("=" * 70)
    print("KVALITETSKONTROLLER")
    print("=" * 70)
    print()
    
    # Test 1: Kapitalisering
    test1 = "detta är en test. detta är en annan mening."
    result1 = normalize_transcript_text(test1)
    print("✅ Kapitalisering test:")
    print(f"   Input:  {test1}")
    print(f"   Output: {result1}")
    print(f"   Status: {'✅ PASS' if result1[0].isupper() and '. Detta' in result1 else '❌ FAIL'}")
    print()
    
    # Test 2: Upprepade ord
    test2 = "det det det är en test och och och vi behöver se"
    result2 = normalize_transcript_text(test2)
    print("✅ Upprepade ord test:")
    print(f"   Input:  {test2}")
    print(f"   Output: {result2}")
    repeated = "det det" in result2 or "och och" in result2
    print(f"   Status: {'✅ PASS' if not repeated else '❌ FAIL'}")
    print()
    
    # Test 3: Kända Whisper-fel
    test3 = "Om vi drare till sin ytterstaspets så ser vi. höjer östen. börja gråta."
    result3 = normalize_transcript_text(test3)
    print("✅ Kända Whisper-fel test:")
    print(f"   Input:  {test3}")
    print(f"   Output: {result3}")
    errors_fixed = "drare" not in result3 and "ytterstaspets" not in result3 and "höjer östen" not in result3
    print(f"   Status: {'✅ PASS' if errors_fixed else '❌ FAIL'}")
    print()
    
    # Test 4: Interpunktion
    test4 = "detta är en mening  .  detta är en annan mening  ,  och detta är en tredje"
    result4 = normalize_transcript_text(test4)
    print("✅ Interpunktion test:")
    print(f"   Input:  {test4}")
    print(f"   Output: {result4}")
    proper_punct = ". " in result4 and ", " in result4 and "  " not in result4
    print(f"   Status: {'✅ PASS' if proper_punct else '❌ FAIL'}")
    print()
    
    print("=" * 70)
    print("REKOMMENDATIONER FÖR FÖRBÄTTRING")
    print("=" * 70)
    print()
    print("Om kvaliteten inte är tillräcklig, överväg:")
    print("1. ✅ Lägg till fler felkorrigeringar baserat på faktiska transkript")
    print("2. ✅ Förbättra grammatikkontroll (svenska regler)")
    print("3. ⚠️  Använd språkmodell för kontextuell korrigering (kräver API)")
    print("4. ✅ Förbättra meningsstruktur och ordning")
    print("5. ✅ Lägg till svenska ordlistor för stavningskontroll")
    print()

if __name__ == "__main__":
    test_enhancement()

