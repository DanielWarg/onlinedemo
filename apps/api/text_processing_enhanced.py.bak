"""
MASTERCLASS: Enhanced transcript normalization with Swedish language support
Avancerad textförbättring med svenska ordlistor, grammatikkontroll och kontextuell korrigering
"""
import re
from typing import List, Tuple, Set
from collections import Counter

# Svenska ordlista (vanliga ord för stavningskontroll)
# I produktion skulle detta kunna laddas från en fil eller bibliotek
SWEDISH_COMMON_WORDS = {
    # Vanliga substantiv
    'konflikt', 'konflikter', 'situation', 'situationer', 'problem', 'problem',
    'arbetsplats', 'människa', 'människor', 'grupp', 'grupper', 'individ', 'individer',
    'kollega', 'kollegor', 'avdelning', 'avdelningar', 'verksamhet', 'syfte',
    'beteende', 'beteenden', 'känsla', 'känslor', 'frustration', 'blockering',
    'önskemål', 'önskemålen', 'behov', 'autonomi', 'rättvisa', 'visshet',
    'dialog', 'exempel', 'illustration', 'kontorsutrymme', 'samtal', 'uppgift',
    'uppgifter', 'stress', 'irritation', 'tolkning', 'uppfattning',
    
    # Vanliga verb
    'är', 'var', 'vara', 'ha', 'har', 'hade', 'kan', 'ska', 'skulle', 'måste',
    'bör', 'börja', 'börjar', 'göra', 'gör', 'gjorde', 'kommer', 'kom',
    'ser', 'såg', 'säger', 'sa', 'talar', 'talade', 'pratar', 'pratade',
    'tänker', 'tänkte', 'känner', 'kände', 'vill', 'ville', 'behöver', 'behövde',
    'finns', 'fanns', 'ligger', 'låg', 'står', 'stod', 'sitter', 'satt',
    'går', 'gick', 'kommer', 'kom', 'blir', 'blev', 'får', 'fick',
    'definierar', 'definierade', 'hänvisar', 'hänvisade', 'illustrerar', 'illustrerade',
    'identifiera', 'identifierade', 'lösa', 'löste', 'flytta', 'flyttade',
    'sätta', 'satte', 'jobba', 'jobbar', 'jobade', 'slutföra', 'slutförde',
    
    # Vanliga adjektiv
    'stor', 'stora', 'liten', 'små', 'bra', 'dålig', 'dåliga', 'viktig', 'viktiga',
    'svår', 'svåra', 'lätt', 'lätta', 'komplex', 'komplexa', 'enkel', 'enkla',
    'varm', 'varma', 'kall', 'kalla', 'ny', 'nya', 'gammal', 'gamla',
    'destruktiv', 'destruktiva', 'frustrerad', 'frustrerade', 'frustrerat',
    'upprörd', 'upprörda', 'nertonad', 'artig', 'artiga',
    
    # Vanliga adverb och konjunktioner
    'mycket', 'lite', 'mer', 'mest', 'mindre', 'minst', 'ofta', 'sällan',
    'alltid', 'aldrig', 'ibland', 'då', 'nu', 'senare', 'tidigare',
    'här', 'där', 'hit', 'dit', 'så', 'då', 'när', 'medan',
    'och', 'eller', 'men', 'för', 'att', 'som', 'när', 'medan',
    'eftersom', 'därför', 'dock', 'emellertid', 'likväl',
    
    # Vanliga prepositioner
    'på', 'i', 'av', 'till', 'från', 'med', 'utan', 'under', 'över',
    'bakom', 'framför', 'bredvid', 'mellan', 'genom', 'mot', 'för',
    
    # Vanliga pronomen
    'jag', 'du', 'han', 'hon', 'den', 'det', 'vi', 'ni', 'de', 'dom',
    'mig', 'dig', 'honom', 'henne', 'oss', 'er', 'dem',
    'min', 'mitt', 'mina', 'din', 'ditt', 'dina', 'hans', 'hennes',
    'vår', 'vårt', 'våra', 'er', 'ert', 'era', 'deras',
    'sig', 'sitt', 'sina', 'varandra',
    
    # Vanliga artiklar och determinanter
    'en', 'ett', 'den', 'det', 'de', 'denna', 'detta', 'dessa',
    'någon', 'något', 'några', 'ingen', 'inget', 'inga',
    'alla', 'allt', 'varje', 'varje', 'samma',
}

# Svenska verbformer (infinitiv -> presens)
SWEDISH_VERB_CONJUGATIONS = {
    'börja': 'börjar',
    'göra': 'gör',
    'komma': 'kommer',
    'se': 'ser',
    'säga': 'säger',
    'tala': 'talar',
    'prata': 'pratar',
    'tänka': 'tänker',
    'känna': 'känner',
    'vilja': 'vill',
    'behöva': 'behöver',
    'ligga': 'ligger',
    'stå': 'står',
    'sitta': 'sitter',
    'gå': 'går',
    'bli': 'blir',
    'få': 'får',
    'definiera': 'definierar',
    'hänvisa': 'hänvisar',
    'illustrera': 'illustrerar',
    'identifiera': 'identifierar',
    'lösa': 'löser',
    'flytta': 'flyttar',
    'sätta': 'sätter',
    'jobba': 'jobbar',
    'slutföra': 'slutför',
}

def _is_swedish_word(word: str) -> bool:
    """Kontrollera om ordet är ett vanligt svenskt ord"""
    word_lower = word.lower().strip('.,!?;:"()[]{}')
    return word_lower in SWEDISH_COMMON_WORDS

def _suggest_correction(word: str) -> str:
    """Föreslå korrigering baserat på likhet med svenska ord"""
    word_lower = word.lower().strip('.,!?;:"()[]{}')
    
    # Kontrollera verbformer
    for infinitive, present in SWEDISH_VERB_CONJUGATIONS.items():
        if word_lower == infinitive:
            return present
        # Levenshtein-liknande kontroll (enkel)
        if len(word_lower) > 3 and word_lower[:3] == infinitive[:3]:
            if abs(len(word_lower) - len(infinitive)) <= 2:
                return present
    
    # Kontrollera vanliga stavfel
    common_typos = {
        'önskimol': 'önskemål',
        'öfomulerade': 'oformulerade',
        'ommedvetna': 'omedvetna',
        'drare': 'drar',
        'hämrisar': 'hänvisar',
        'förypa': 'fördjupa',
    }
    
    if word_lower in common_typos:
        return common_typos[word_lower]
    
    return word  # Ingen korrigering hittad

def _fix_verb_forms(text: str) -> str:
    """Fixa vanliga verbformfel"""
    # "börja gråta" -> "börjar gråta"
    text = re.sub(r'\bbörja (gråta|prata|tala|jobba)\b', r'börjar \1', text, flags=re.IGNORECASE)
    
    # "göra ett bra jobb" -> "gör ett bra jobb" (men behåll "göra" i andra sammanhang)
    text = re.sub(r'\bgöra (ett|en) (bra|dåligt) (jobb|arbete)\b', r'gör \1 \2 \3', text, flags=re.IGNORECASE)
    
    return text

def _improve_sentence_structure(text: str) -> str:
    """Förbättra meningsstruktur"""
    # Fix "det är en X består" -> "en X består"
    text = re.sub(r'\bdet är en (\w+) består\b', r'en \1 består', text, flags=re.IGNORECASE)
    
    # Fix "det är det" -> "det är"
    text = re.sub(r'\bdet är det\b', 'det är', text, flags=re.IGNORECASE)
    
    # Fix "det här är" -> "detta är"
    text = re.sub(r'\bdet här är\b', 'detta är', text, flags=re.IGNORECASE)
    
    # Fix "det här" -> "detta"
    text = re.sub(r'\bdet här\b', 'detta', text, flags=re.IGNORECASE)
    
    # Fix "inom form av" -> "i form av"
    text = re.sub(r'\binom form av\b', 'i form av', text, flags=re.IGNORECASE)
    
    # Fix "sån" -> "sådan"
    text = re.sub(r'\bsån\b', 'sådan', text, flags=re.IGNORECASE)
    
    return text

def _enhance_punctuation(text: str) -> str:
    """Förbättra interpunktion och kapitalisering"""
    # Capitalize first letter
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    
    # Capitalize after sentence endings
    text = re.sub(r'([.!?])\s+([a-zåäö])', lambda m: m.group(1) + ' ' + m.group(2).upper(), text)
    
    # Fix spacing around punctuation
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)  # Remove space before punctuation
    text = re.sub(r'([.,!?;:])([^\s])', r'\1 \2', text)  # Add space after punctuation
    text = re.sub(r'([.,!?;:])\s+([.,!?;:])', r'\1', text)  # Remove multiple punctuation
    
    # Normalize quotes
    text = re.sub(r'["""]', '"', text)
    text = re.sub(r'[''']', "'", text)
    
    return text

def enhance_transcript_masterclass(raw_text: str) -> str:
    """
    MASTERCLASS: Enhanced transcript normalization
    
    Avancerad textförbättring med:
    - Svenska ordlistor för stavningskontroll
    - Verbform-korrigering
    - Meningsstruktur-förbättring
    - Avancerad interpunktion
    - Kontextuell korrigering
    
    NEVER log raw_text or output.
    """
    if not raw_text:
        return ""
    
    text = raw_text
    
    # Steg 1: Grundläggande normalisering (från normalize_transcript_text)
    from text_processing import normalize_transcript_text
    text = normalize_transcript_text(text)
    
    # Steg 2: Verbform-korrigering
    text = _fix_verb_forms(text)
    
    # Steg 3: Meningsstruktur-förbättring
    text = _improve_sentence_structure(text)
    
    # Steg 4: Avancerad interpunktion
    text = _enhance_punctuation(text)
    
    # Steg 5: Stavningskontroll (identifiera okända ord)
    words = re.findall(r'\b\w+\b', text)
    for word in words:
        if len(word) > 3 and not _is_swedish_word(word):
            # Okänt ord - försök korrigera
            correction = _suggest_correction(word)
            if correction != word:
                text = re.sub(r'\b' + re.escape(word) + r'\b', correction, text, flags=re.IGNORECASE)
    
    # Steg 6: Final whitespace normalization
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

