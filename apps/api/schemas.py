from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from models import Classification, NoteCategory, SourceType, ProjectStatus


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    classification: Classification = Classification.NORMAL
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    classification: Optional[Classification] = None
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None


class ProjectStatusUpdate(BaseModel):
    status: ProjectStatus


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    classification: str
    status: str
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectEventCreate(BaseModel):
    event_type: str
    actor: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ProjectEventResponse(BaseModel):
    id: int
    project_id: int
    event_type: str
    timestamp: datetime
    actor: Optional[str]
    metadata: Optional[Dict[str, Any]] = Field(alias="event_metadata")

    class Config:
        from_attributes = True
        populate_by_name = True


class DocumentUpdate(BaseModel):
    masked_text: str  # Updated masked text (will be re-sanitized)

class DocumentResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    file_type: str
    classification: str
    masked_text: str
    sanitize_level: str
    usage_restrictions: dict
    pii_gate_reasons: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    file_type: str
    classification: str
    sanitize_level: str
    usage_restrictions: dict
    pii_gate_reasons: Optional[dict] = None
    created_at: datetime
    # NO masked_text in list

    class Config:
        from_attributes = True


# Project Notes schemas
class NoteCreate(BaseModel):
    title: Optional[str] = None
    body: str  # Raw body text (will be sanitized)

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    body: str  # Raw body text (will be sanitized)


class NoteResponse(BaseModel):
    id: int
    project_id: int
    title: Optional[str]
    masked_body: str  # Sanitized body
    sanitize_level: str
    pii_gate_reasons: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NoteListResponse(BaseModel):
    id: int
    project_id: int
    title: Optional[str]
    sanitize_level: str
    created_at: datetime
    # NO masked_body in list

    class Config:
        from_attributes = True


# Journalist Notes schemas (raw text, no sanitization)
class JournalistNoteCreate(BaseModel):
    title: Optional[str] = None  # Optional title/name
    body: str  # Raw body text (will be technically sanitized only)
    category: Optional[NoteCategory] = NoteCategory.RAW


class JournalistNoteUpdate(BaseModel):
    title: Optional[str] = None
    body: str  # Raw body text (will be technically sanitized only)
    category: Optional[NoteCategory] = None


class JournalistNoteResponse(BaseModel):
    id: int
    project_id: int
    title: Optional[str]
    body: str  # Raw body (no masking)
    category: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JournalistNoteListResponse(BaseModel):
    id: int
    project_id: int
    title: Optional[str]
    preview: str  # First line of body or title
    category: str
    created_at: datetime
    updated_at: datetime
    # NO body in list

    class Config:
        from_attributes = True


class JournalistNoteImageResponse(BaseModel):
    id: int
    note_id: int
    filename: str
    mime_type: str
    created_at: datetime

    class Config:
        from_attributes = True


# Project Sources schemas
class ProjectSourceCreate(BaseModel):
    title: str = Field(..., max_length=200)
    type: SourceType
    url: Optional[str] = None
    comment: Optional[str] = Field(None, max_length=500)


class ProjectSourceUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    comment: Optional[str] = None

class ProjectSourceResponse(BaseModel):
    id: int
    project_id: int
    title: str
    type: str
    url: Optional[str]
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Scout schemas
class ScoutFeedCreate(BaseModel):
    name: str
    url: str


class ScoutFeedUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    is_enabled: Optional[bool] = None


class ScoutFeedResponse(BaseModel):
    id: int
    name: str
    url: str
    is_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Async jobs (metadata-only)
class AiJobResponse(BaseModel):
    id: int
    kind: str
    status: str
    progress: int
    project_id: Optional[int] = None
    actor: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ScoutItemResponse(BaseModel):
    id: int
    feed_id: int
    title: str
    link: str
    published_at: Optional[datetime]
    fetched_at: datetime
    raw_source: str

    class Config:
        from_attributes = True


# Feed Import schemas
class FeedItemPreview(BaseModel):
    guid: str
    title: str
    link: str
    published: Optional[str] = None
    summary_text: str


class FeedPreviewResponse(BaseModel):
    title: str
    description: str
    items: List[FeedItemPreview]


class CreateProjectFromFeedRequest(BaseModel):
    url: str
    project_name: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=100)
    mode: Optional[str] = Field(default="fulltext")  # "fulltext" or "summary"


class CreateProjectFromFeedResponse(BaseModel):
    project_id: int
    created_count: int  # Documents created
    created_notes: int  # ProjectNotes created
    created_sources: int  # ProjectSources created
    skipped_duplicates: int


class CreateProjectFromScoutItemRequest(BaseModel):
    scout_item_id: int
    project_name: Optional[str] = None


class CreateProjectFromScoutItemResponse(BaseModel):
    project_id: int
    document_id: int


# Fort Knox schemas
class KnoxPolicy(BaseModel):
    """Fort Knox policy definition."""
    policy_id: str  # e.g., "internal", "external"
    policy_version: str
    ruleset_hash: str
    mode: Literal["internal", "external"]
    sanitize_min_level: str  # "normal", "strict", "paranoid"
    quote_limit_words: int
    date_strictness: str  # e.g., "strict", "relaxed"
    max_bytes: int


class KnoxDocumentItem(BaseModel):
    """Document item in KnoxInputPack."""
    doc_id: int
    sha256: str
    sanitize_level: str
    updated_at: datetime
    masked_text: str


class KnoxNoteItem(BaseModel):
    """Note item in KnoxInputPack."""
    note_id: int
    sha256: str
    sanitize_level: str
    updated_at: datetime
    masked_body: str


class KnoxSourceItem(BaseModel):
    """Source item in KnoxInputPack (v1: metadata only, no URL in payload)."""
    source_id: int
    type: str
    title: str


class KnoxInputPack(BaseModel):
    """Deterministic input pack for Fort Knox compilation."""
    project: Dict[str, Any]  # {id, name, tags, status, created_at}
    documents: List[KnoxDocumentItem]
    notes: List[KnoxNoteItem]
    sources: List[KnoxSourceItem]  # v1: metadata only
    policy: KnoxPolicy
    template_id: str
    input_manifest: List[Dict[str, Any]]  # Manifest utan innehåll
    input_fingerprint: str  # sha256(canonical_json(input_manifest))


class SelectionItem(BaseModel):
    """Single selection item for External compile (iteration 1: documents + notes)."""
    type: Literal["document", "note"]
    id: int


class SelectionSet(BaseModel):
    """Selection for include/exclude lists. Deterministic order is maintained by backend."""
    include: List[SelectionItem] = []
    exclude: List[SelectionItem] = []


class KnoxCompileRequest(BaseModel):
    """Request to compile a Fort Knox report."""
    project_id: int
    policy_id: str
    template_id: str
    selection: Optional[SelectionSet] = None
    snapshot_mode: bool = False


class KnoxErrorResponse(BaseModel):
    """Metadata-only error response."""
    error_code: str
    reasons: List[str]
    detail: Optional[str] = None


class KnoxThemeItem(BaseModel):
    """Theme item in LLM response."""
    name: str
    bullets: List[str]


class KnoxRiskItem(BaseModel):
    """Risk item in LLM response."""
    risk: str
    mitigation: str


class KnoxLLMResponse(BaseModel):
    """Strict JSON Schema for LLM response (additionalProperties:false)."""
    template_id: str
    language: Literal["sv"]
    title: str
    executive_summary: str
    themes: List[KnoxThemeItem]
    timeline_high_level: List[str]  # string[] not string
    risks: List[KnoxRiskItem]
    open_questions: List[str]
    next_steps: List[str]
    confidence: Literal["low", "medium", "high"]

    class Config:
        extra = "forbid"  # additionalProperties:false equivalent


class KnoxReportResponse(BaseModel):
    """Fort Knox report response."""
    id: int
    project_id: int
    policy_id: str
    policy_version: str
    ruleset_hash: str
    template_id: str
    engine_id: Optional[str]
    input_fingerprint: str
    input_manifest: List[Dict[str, Any]]  # Manifest utan innehåll
    gate_results: Dict[str, Any]
    rendered_markdown: Optional[str]  # Endast vid pass
    created_at: datetime
    latency_ms: Optional[int]

    class Config:
        from_attributes = True
