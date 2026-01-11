from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Enum as SQLEnum, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from database import Base


class Classification(str, enum.Enum):
    NORMAL = "normal"
    SENSITIVE = "sensitive"
    SOURCE_SENSITIVE = "source-sensitive"


class SanitizeLevel(str, enum.Enum):
    NORMAL = "normal"
    STRICT = "strict"
    PARANOID = "paranoid"


class ProjectStatus(str, enum.Enum):
    RESEARCH = "research"
    PROCESSING = "processing"
    FACT_CHECK = "fact_check"
    READY = "ready"
    ARCHIVED = "archived"


class SourceType(str, enum.Enum):
    LINK = "link"          # Länk
    PERSON = "person"      # Person
    DOCUMENT = "document"  # Dokument
    OTHER = "other"        # Övrigt


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    classification = Column(SQLEnum(Classification), default=Classification.NORMAL, nullable=False)
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.RESEARCH, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    tags = Column(JSON, nullable=True)  # List of strings
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    events = relationship("ProjectEvent", back_populates="project", order_by="ProjectEvent.timestamp.desc()")
    documents = relationship("Document", back_populates="project", order_by="Document.created_at.desc()")
    notes = relationship("ProjectNote", back_populates="project", order_by="ProjectNote.created_at.desc()")
    journalist_notes = relationship("JournalistNote", back_populates="project", order_by="JournalistNote.updated_at.desc()")
    sources = relationship("ProjectSource", back_populates="project", order_by="ProjectSource.created_at.desc()")


class ProjectEvent(Base):
    __tablename__ = "project_events"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    event_type = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    actor = Column(String, nullable=True)
    event_metadata = Column("metadata", JSON, nullable=True)

    project = relationship("Project", back_populates="events")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # 'pdf' or 'txt'
    classification = Column(SQLEnum(Classification), nullable=False)
    masked_text = Column(Text, nullable=False)
    file_path = Column(String, nullable=False)  # Server-side only, never exposed
    sanitize_level = Column(SQLEnum(SanitizeLevel), default=SanitizeLevel.NORMAL, nullable=False)
    usage_restrictions = Column(JSON, nullable=False, default=lambda: {"ai_allowed": True, "export_allowed": True})
    pii_gate_reasons = Column(JSON, nullable=True)  # {"normal": [...], "strict": [...]}
    document_metadata = Column("metadata", JSON, nullable=True)  # {"source_type": "feed", "feed_url": "...", "item_guid": "...", "item_link": "...", "published": "..."}
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="documents")


class ProjectNote(Base):
    """Project notes with same sanitization as documents."""
    __tablename__ = "project_notes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=True)  # Optional title
    masked_body = Column(Text, nullable=False)  # Masked/sanitized body text
    sanitize_level = Column(SQLEnum(SanitizeLevel), default=SanitizeLevel.NORMAL, nullable=False)
    pii_gate_reasons = Column(JSON, nullable=True)
    usage_restrictions = Column(JSON, nullable=True)  # Same as Document: {"ai_allowed": bool, "export_allowed": bool}
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="notes")


class NoteCategory(str, enum.Enum):
    RAW = "raw"  # Råanteckning
    WORK = "work"  # Arbetsanteckning
    REFLECTION = "reflection"  # Reflektion
    QUESTION = "question"  # Fråga
    SOURCE = "source"  # Källa
    OTHER = "other"  # Övrigt


class JournalistNote(Base):
    """Journalist notes - raw text, no sanitization, no AI processing."""
    __tablename__ = "journalist_notes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=True)  # Optional title/name for the note
    body = Column(Text, nullable=False)  # Raw text - only technical sanitization (no masking, no normalization)
    category = Column(SQLEnum(NoteCategory), default=NoteCategory.RAW, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="journalist_notes")
    images = relationship("JournalistNoteImage", back_populates="note", cascade="all, delete-orphan")


class JournalistNoteImage(Base):
    """Images attached to journalist notes - private references only."""
    __tablename__ = "journalist_note_images"

    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey("journalist_notes.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String, nullable=False)  # Server-side only, never exposed
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    note = relationship("JournalistNote", back_populates="images")


class ProjectSource(Base):
    """Källor/Referenser - manuella metadata för journalistisk försvarbarhet."""
    __tablename__ = "project_sources"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)  # Kort, manuell titel
    type = Column(SQLEnum(SourceType), nullable=False)
    url = Column(String, nullable=True)  # URL för länk-källor (first-class field)
    comment = Column(String, nullable=True)  # Valfri, kort kommentar
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="sources")


class ScoutFeed(Base):
    """RSS feeds för Scout-funktionalitet."""
    __tablename__ = "scout_feeds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)  # Kan vara placeholder/tom
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ScoutItem(Base):
    """RSS items från Scout feeds."""
    __tablename__ = "scout_items"

    id = Column(Integer, primary_key=True, index=True)
    feed_id = Column(Integer, ForeignKey("scout_feeds.id"), nullable=False)
    title = Column(String, nullable=False)
    link = Column(String, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    guid_hash = Column(String, unique=True, nullable=False, index=True)
    raw_source = Column(String, nullable=False)  # Snapshot av feed.name vid fetch


class KnoxReport(Base):
    """Fort Knox-rapporter - deterministiska sammanställningar från projekt."""
    __tablename__ = "knox_reports"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    policy_id = Column(String, nullable=False)  # e.g., "internal", "external"
    policy_version = Column(String, nullable=False)
    ruleset_hash = Column(String, nullable=False)
    template_id = Column(String, nullable=False)  # e.g., "weekly", "brief", "incident"
    engine_id = Column(String, nullable=True)  # e.g., "ministral-3-8b-gguf-q4_k_m"
    input_fingerprint = Column(String, nullable=False)  # sha256 of canonical manifest
    input_manifest = Column(JSON, nullable=False)  # Manifest utan innehåll
    gate_results = Column(JSON, nullable=False)  # {"input": {"pass": bool, "reasons": []}, "output": {...}}
    rendered_markdown = Column(Text, nullable=True)  # Endast vid pass, null vid fail
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    latency_ms = Column(Integer, nullable=True)  # Latency i millisekunder

    # Index för idempotens lookup (engine_id ingår i app-logik, men fingerprint är huvudnyckeln)
    __table_args__ = (
        Index('idx_knox_report_idempotency', 'project_id', 'policy_id', 'template_id', 'input_fingerprint'),
    )


class AiJobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AiJob(Base):
    """Bakgrundsjobb (STT/LLM) med metadata-only payload/result."""
    __tablename__ = "ai_jobs"

    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String, nullable=False)  # e.g. "fortknox_compile", "recording_transcribe"
    status = Column(SQLEnum(AiJobStatus), default=AiJobStatus.QUEUED, nullable=False)
    progress = Column(Integer, default=0, nullable=False)  # 0..100 (best effort)

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    actor = Column(String, nullable=True)

    payload = Column(JSON, nullable=True)  # metadata-only request payload
    result = Column(JSON, nullable=True)   # metadata-only result payload (ids, timings)

    error_code = Column(String, nullable=True)
    error_detail = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
