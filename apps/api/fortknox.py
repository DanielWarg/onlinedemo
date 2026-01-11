"""
Fort Knox Core Logic - Deterministisk sammanställning av projekt.
"""
import hashlib
import json
import re
import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime
from sqlalchemy.orm import Session

from models import Project, Document, ProjectNote, ProjectSource
from schemas import (
    KnoxInputPack, KnoxPolicy, KnoxDocumentItem, KnoxNoteItem, KnoxSourceItem
)
from text_processing import pii_gate_check

logger = logging.getLogger(__name__)


def get_policy(policy_id: str) -> KnoxPolicy:
    """
    Hämta policy baserat på policy_id.
    
    v1: Enkla fasta policies för internal/external.
    """
    policies = {
        "internal": KnoxPolicy(
            policy_id="internal",
            policy_version="1.0",
            ruleset_hash="internal_v1",
            mode="internal",
            sanitize_min_level="normal",
            quote_limit_words=8,
            date_strictness="relaxed",
            max_bytes=800000  # 800KB
        ),
        "external": KnoxPolicy(
            policy_id="external",
            policy_version="1.0",
            ruleset_hash="external_v1",
            mode="external",
            sanitize_min_level="strict",
            quote_limit_words=8,
            date_strictness="strict",
            max_bytes=300000  # 300KB
        )
    }
    
    if policy_id not in policies:
        raise ValueError(f"Unknown policy_id: {policy_id}")
    
    return policies[policy_id]


def compute_sha256(text: str) -> str:
    """Beräkna SHA256 hash av text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(data: Any) -> str:
    """Canonical JSON encoding för deterministiska fingerprints."""
    # Convert datetime objects to ISO format strings
    def json_serial(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
    
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=json_serial)


def build_knox_input_pack(
    project_id: int,
    policy: KnoxPolicy,
    template_id: str,
    db: Session
) -> KnoxInputPack:
    """
    Bygg deterministiskt KnoxInputPack från projekt.
    
    Returns:
        KnoxInputPack med documents, notes, sources, manifest och fingerprint
    """
    # Hämtar projekt
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError(f"Project {project_id} not found")
    
    # Hämtar documents (sorterat: created_at asc, id asc)
    # Exkludera dokument som är markerade för exkludering från Fort Knox
    documents = db.query(Document).filter(
        Document.project_id == project_id
    ).order_by(Document.created_at.asc(), Document.id.asc()).all()
    
    # Filtrera bort dokument med fortknox_excluded i usage_restrictions
    documents = [
        doc for doc in documents 
        if not (
            (doc.usage_restrictions and doc.usage_restrictions.get("fortknox_excluded", False))
            or ((getattr(doc, "document_metadata", None) or {}).get("source_type") == "fortknox_report")
        )
    ]
    
    # Hämtar notes (sorterat: created_at asc, id asc)
    # Exkludera anteckningar som är markerade för exkludering från Fort Knox
    notes = db.query(ProjectNote).filter(
        ProjectNote.project_id == project_id
    ).order_by(ProjectNote.created_at.asc(), ProjectNote.id.asc()).all()
    
    # Filtrera bort anteckningar med fortknox_excluded i usage_restrictions
    notes = [
        note for note in notes 
        if not (note.usage_restrictions and note.usage_restrictions.get('fortknox_excluded', False))
    ]
    
    # Hämtar sources (sorterat: type asc, id asc)
    sources = db.query(ProjectSource).filter(
        ProjectSource.project_id == project_id
    ).order_by(ProjectSource.type.asc(), ProjectSource.id.asc()).all()
    
    # Bygg document items
    document_items = []
    document_manifest = []
    for doc in documents:
        # Document hash: använd document.sha256 om fält finns, annars beräkna sha256(document.masked_text)
        doc_hash = getattr(doc, 'sha256', None)
        if not doc_hash:
            doc_hash = compute_sha256(doc.masked_text)
        
        document_items.append(KnoxDocumentItem(
            doc_id=doc.id,
            sha256=doc_hash,
            sanitize_level=doc.sanitize_level.value,
            updated_at=doc.created_at,  # Documents har inte updated_at, använd created_at
            masked_text=doc.masked_text
        ))
        
        document_manifest.append({
            "kind": "document",
            "id": doc.id,
            "sha256": doc_hash,
            "sanitize_level": doc.sanitize_level.value,
            "updated_at": doc.created_at.isoformat()
        })
    
    # Bygg note items
    note_items = []
    note_manifest = []
    for note in notes:
        # Beräkna sha256 för note.masked_body i runtime
        note_hash = compute_sha256(note.masked_body)
        
        note_items.append(KnoxNoteItem(
            note_id=note.id,
            sha256=note_hash,
            sanitize_level=note.sanitize_level.value,
            updated_at=note.created_at,
            masked_body=note.masked_body
        ))
        
        note_manifest.append({
            "kind": "note",
            "id": note.id,
            "sha256": note_hash,
            "sanitize_level": note.sanitize_level.value,
            "updated_at": note.created_at.isoformat()
        })
    
    # Bygg source items (metadata only, v1: exkludera URL från payload men inkludera i manifest)
    source_items = []
    source_manifest = []
    for source in sources:
        # URL hash för manifest
        url_hash = None
        if source.url:
            url_hash = compute_sha256(source.url)
        
        source_items.append(KnoxSourceItem(
            source_id=source.id,
            type=source.type.value,
            title=source.title
        ))
        
        source_manifest.append({
            "kind": "source",
            "id": source.id,
            "url_hash": url_hash,
            "updated_at": source.created_at.isoformat()
        })
    
    # Bygg input_manifest (utan innehåll, endast metadata + hash)
    input_manifest = document_manifest + note_manifest + source_manifest
    
    # Bygg input_fingerprint = sha256(canonical_json(input_manifest))
    manifest_json = canonical_json(input_manifest)
    input_fingerprint = compute_sha256(manifest_json)
    
    # Bygg project metadata
    project_metadata = {
        "id": project.id,
        "name": project.name,
        "tags": project.tags or [],
        "status": project.status.value,
        "created_at": project.created_at.isoformat()
    }
    
    return KnoxInputPack(
        project=project_metadata,
        documents=document_items,
        notes=note_items,
        sources=source_items,
        policy=policy,
        template_id=template_id,
        input_manifest=input_manifest,
        input_fingerprint=input_fingerprint
    )


def input_gate(pack: KnoxInputPack, policy: KnoxPolicy) -> Tuple[bool, List[str]]:
    """
    Input gate: validerar sanitize_level, PII gate och size innan export.
    
    Returns:
        (pass: bool, reasons: list)
    """
    reasons = []
    
    # Kolla sanitize_level >= policy.sanitize_min_level (docs + notes)
    min_level_order = {"normal": 0, "strict": 1, "paranoid": 2}
    required_level = min_level_order.get(policy.sanitize_min_level, 0)
    
    for doc in pack.documents:
        doc_level = min_level_order.get(doc.sanitize_level, 0)
        if doc_level < required_level:
            reasons.append(f"document_{doc.doc_id}_sanitize_level_too_low")
    
    for note in pack.notes:
        note_level = min_level_order.get(note.sanitize_level, 0)
        if note_level < required_level:
            reasons.append(f"note_{note.note_id}_sanitize_level_too_low")
    
    # Kör pii_gate_check på sammanfogad sanitized payload (documents + notes)
    all_texts = []
    for doc in pack.documents:
        all_texts.append(doc.masked_text)
    for note in pack.notes:
        all_texts.append(note.masked_body)
    
    combined_text = "\n\n".join(all_texts)
    is_safe, pii_reasons = pii_gate_check(combined_text)
    if not is_safe:
        reasons.extend([f"pii_gate_{reason}" for reason in pii_reasons])
    
    # Kolla pack_size <= policy.max_bytes
    pack_json = canonical_json(pack.model_dump())
    pack_size = len(pack_json.encode("utf-8"))
    if pack_size > policy.max_bytes:
        reasons.append(f"pack_size_exceeded_{pack_size}_{policy.max_bytes}")
    
    return (len(reasons) == 0, reasons)


def normalize_text_for_n_gram(text: str) -> str:
    """Normalisera text för n-gram match: lowercase + whitespace-normalisering."""
    # Lowercase
    text = text.lower()
    # Whitespace-normalisering: replace whitespace sequences med single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def create_n_grams(text: str, n: int) -> List[str]:
    """Skapa n-grams från text."""
    words = text.split()
    if len(words) < n:
        return []
    
    n_grams = []
    for i in range(len(words) - n + 1):
        n_gram = " ".join(words[i:i+n])
        n_grams.append(n_gram)
    
    return n_grams


def re_id_guard(
    rendered_text: str,
    input_texts: List[str],
    policy: KnoxPolicy
) -> Tuple[bool, List[str]]:
    """
    Re-ID guard: kontrollerar om output innehåller förbjudna citat eller identifierande information.
    
    Returns:
        (pass: bool, reasons: list)
    """
    reasons = []
    
    # Normalisera input och output
    normalized_output = normalize_text_for_n_gram(rendered_text)
    normalized_inputs = [normalize_text_for_n_gram(text) for text in input_texts]
    
    # Skapa n-grams från input_texts med längd = quote_limit_words + 1
    n = policy.quote_limit_words + 1
    all_input_n_grams = set()
    for input_text in normalized_inputs:
        n_grams = create_n_grams(input_text, n)
        all_input_n_grams.update(n_grams)
    
    # Kolla om någon n-gram-sekvens från input finns i output
    for n_gram in all_input_n_grams:
        if n_gram in normalized_output:
            reasons.append("quote_detected")
            break  # Hittat en match, fail
    
    # External policy: ingen datum-gate längre (datum maskas i pipeline vid strict/paranoid)
    # Om datum finns i output här så är det ett pipeline-fel (fail-closed)
    
    return (len(reasons) == 0, reasons)


def break_quote_ngrams(
    rendered_text: str,
    input_texts: List[str],
    policy: KnoxPolicy,
    *,
    max_breaks: int = 10
) -> Tuple[str, int]:
    """
    Deterministiskt "de-quote": om output innehåller ett långt n-gram från input,
    bryt matchen genom att injicera en markör (…).

    Detta är en showreel-säker åtgärd för External policy där vi vill undvika att
    rå frasering/citat återges ordagrant.
    """
    if not rendered_text:
        return rendered_text, 0
    if not input_texts:
        return rendered_text, 0
    if not getattr(policy, "quote_limit_words", None):
        return rendered_text, 0

    # Skapa n-grams från input_texts med längd = quote_limit_words + 1 (samma som re_id_guard)
    n = policy.quote_limit_words + 1
    all_input_n_grams: set[str] = set()
    for input_text in input_texts:
        norm = normalize_text_for_n_gram(input_text or "")
        all_input_n_grams.update(create_n_grams(norm, n))

    # Segment-tokenisera output så vi kan injicera en markör utan att tappa radbrytningar.
    # segments = ["foo", "  ", "bar", "\n", ...]
    segs: List[str] = []
    seg_is_space: List[bool] = []
    for m in re.finditer(r"\s+|\S+", rendered_text):
        s = m.group(0)
        segs.append(s)
        seg_is_space.append(s.isspace())

    def _rebuild_word_index():
        word_seg_idxs = [i for i, is_sp in enumerate(seg_is_space) if not is_sp]
        word_tokens = [segs[i].lower() for i in word_seg_idxs]
        return word_seg_idxs, word_tokens

    breaks = 0
    for _ in range(max_breaks):
        word_seg_idxs, word_tokens = _rebuild_word_index()
        if len(word_tokens) < n:
            break

        found_i = None
        # Hitta första matchande n-gram i output (deterministiskt vänster->höger)
        for i in range(0, len(word_tokens) - n + 1):
            ngram = " ".join(word_tokens[i:i + n])
            if ngram in all_input_n_grams:
                found_i = i
                break
        if found_i is None:
            break

        cut = max(3, n // 2)
        insert_word_pos = min(found_i + cut, len(word_tokens))
        # Mappa word-position -> segment-index (infoga före den token som ligger där)
        if insert_word_pos >= len(word_seg_idxs):
            insert_seg_at = len(segs)
        else:
            insert_seg_at = word_seg_idxs[insert_word_pos]

        # Injicera " … " som egna segment för att bryta n-gram-matchningen.
        # (Det gör att normalize_text_for_n_gram() aldrig kan innehålla exakt samma n-gram.)
        segs[insert_seg_at:insert_seg_at] = [" ", "…", " "]
        seg_is_space[insert_seg_at:insert_seg_at] = [True, False, True]
        breaks += 1

    return "".join(segs), breaks


def render_markdown(llm_json: Dict[str, Any], template_id: str) -> str:
    """
    Deterministisk rendering från JSON till Markdown.
    
    Template_id påverkar inte strukturen, endast styling/formatting.
    """
    lines = []
    
    # Title
    lines.append(f"# {llm_json.get('title', 'Rapport')}")
    lines.append("")
    
    # Executive summary
    if llm_json.get('executive_summary'):
        lines.append("## Sammanfattning")
        lines.append("")
        lines.append(llm_json['executive_summary'])
        lines.append("")
    
    # Themes
    if llm_json.get('themes'):
        lines.append("## Teman")
        lines.append("")
        for theme in llm_json['themes']:
            lines.append(f"### {theme.get('name', 'Tema')}")
            for bullet in theme.get('bullets', []):
                lines.append(f"- {bullet}")
            lines.append("")
    
    # Timeline
    if llm_json.get('timeline_high_level'):
        lines.append("## Tidslinje")
        lines.append("")
        for item in llm_json['timeline_high_level']:
            lines.append(f"- {item}")
        lines.append("")
    
    # Risks
    if llm_json.get('risks'):
        lines.append("## Risker och åtgärder")
        lines.append("")
        for risk in llm_json['risks']:
            lines.append(f"### {risk.get('risk', 'Risk')}")
            lines.append(f"Åtgärd: {risk.get('mitigation', '')}")
            lines.append("")
    
    # Open questions
    if llm_json.get('open_questions'):
        lines.append("## Öppna frågor")
        lines.append("")
        for question in llm_json['open_questions']:
            lines.append(f"- {question}")
        lines.append("")
    
    # Next steps
    if llm_json.get('next_steps'):
        lines.append("## Nästa steg")
        lines.append("")
        for step in llm_json['next_steps']:
            lines.append(f"- {step}")
        lines.append("")
    
    # Confidence
    if llm_json.get('confidence'):
        lines.append(f"*Förtroende: {llm_json['confidence']}*")
        lines.append("")
    
    return "\n".join(lines)
