ARCHIVED: replaced by docs/VERIFYING.md, docs/ARCHITECTURE.md, docs/SECURITY.md

# Källor / Referenser (Byggsten B) — Implementation Report

**Status:** ✅ Completed  
**Datum:** 2026-01-03  
**Verifiering:** 7/7 Backend PASS, Browser E2E PASS

---

## Scope (låst)

Lägg till källhantering för journalistisk försvarbarhet. Källor är metadata som lagras separat från innehåll. Ingen automatik, ingen AI, ingen koppling till Scout.

---

## Backend ändringar

### 1. Database model: `apps/api/models.py`

**Lägg till enum** (efter line 17, efter `SanitizeLevel`):
```python
class SourceType(str, enum.Enum):
    LINK = "link"          # Länk
    PERSON = "person"      # Person
    DOCUMENT = "document"  # Dokument
    OTHER = "other"        # Övrigt
```

**Lägg till modell** (efter `JournalistNoteImage`, line 121):
```python
class ProjectSource(Base):
    """Källor/Referenser - manuella metadata för journalistisk försvarbarhet."""
    __tablename__ = "project_sources"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)  # Kort, manuell titel
    type = Column(SQLEnum(SourceType), nullable=False)
    comment = Column(String, nullable=True)  # Valfri, kort kommentar
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="sources")
```

**Lägg till relationship i Project** (line 35, efter `journalist_notes`):
```python
sources = relationship("ProjectSource", back_populates="project", order_by="ProjectSource.created_at.desc()")
```

### 2. API schemas: `apps/api/schemas.py`

**Import** (line 4):
```python
from models import Classification, NoteCategory, SourceType
```

**Lägg till schemas** (efter `JournalistNoteImageResponse`, line 168):
```python
# Project Sources schemas
class ProjectSourceCreate(BaseModel):
    title: str = Field(..., max_length=200)
    type: SourceType
    comment: Optional[str] = Field(None, max_length=500)

class ProjectSourceResponse(BaseModel):
    id: int
    project_id: int
    title: str
    type: str
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
```

### 3. API endpoints: `apps/api/main.py`

**Import** (line 37, uppdatera):
```python
from models import Project, ProjectEvent, Document, ProjectNote, JournalistNote, JournalistNoteImage, ProjectSource, Base, Classification, SanitizeLevel, NoteCategory, SourceType
```

**Import** (line 39, uppdatera):
```python
from schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectEventCreate, ProjectEventResponse,
    DocumentResponse, DocumentListResponse, NoteCreate, NoteResponse, NoteListResponse,
    JournalistNoteCreate, JournalistNoteUpdate, JournalistNoteResponse, JournalistNoteListResponse,
    JournalistNoteImageResponse, ProjectSourceCreate, ProjectSourceResponse
)
```

**Lägg till endpoints** (efter journalist notes endpoints, ca line 600):
```python
# ===== PROJECT SOURCES ENDPOINTS =====

@app.post("/api/projects/{project_id}/sources", response_model=ProjectSourceResponse, status_code=201)
async def create_project_source(
    project_id: int,
    source_data: ProjectSourceCreate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Create a new source/reference for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create source
    source = ProjectSource(
        project_id=project_id,
        title=source_data.title,
        type=source_data.type,
        comment=source_data.comment
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    
    # Log event (metadata only: type + timestamp, NO title/comment)
    event_metadata = _safe_event_metadata({
        "type": source_data.type.value
    }, context="audit")
    
    event = ProjectEvent(
        project_id=project_id,
        event_type="source_added",
        actor=username,
        event_metadata=event_metadata
    )
    db.add(event)
    db.commit()
    
    logger.info(f"Source added to project {project_id}: type={source_data.type.value}")
    
    return source


@app.get("/api/projects/{project_id}/sources", response_model=List[ProjectSourceResponse])
async def get_project_sources(
    project_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Get all sources for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    sources = db.query(ProjectSource).filter(ProjectSource.project_id == project_id).order_by(ProjectSource.created_at.desc()).all()
    return sources


@app.delete("/api/projects/{project_id}/sources/{source_id}", status_code=204)
async def delete_project_source(
    project_id: int,
    source_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Delete a source (hard delete)."""
    source = db.query(ProjectSource).filter(
        ProjectSource.id == source_id,
        ProjectSource.project_id == project_id
    ).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    source_type = source.type.value
    
    # Delete source
    db.delete(source)
    db.commit()
    
    # Log event (metadata only: type, NO title/comment)
    event_metadata = _safe_event_metadata({
        "type": source_type
    }, context="audit")
    
    event = ProjectEvent(
        project_id=project_id,
        event_type="source_removed",
        actor=username,
        event_metadata=event_metadata
    )
    db.add(event)
    db.commit()
    
    logger.info(f"Source removed from project {project_id}: type={source_type}")
    
    return None
```

### 4. Verification script: `apps/api/_verify/verify_project_sources.py`

**Status:** ✅ **7/7 PASS**

Test coverage:
1. ✅ Create project
2. ✅ Add source (type: link)
3. ✅ Add source (type: person)
4. ✅ Get all sources (should be 2)
5. ✅ Verify events (no title/comment in metadata)
6. ✅ Delete source
7. ✅ Verify source is gone (should be 1 left)

---

## Frontend ändringar

### 5. UI component: `apps/web/src/pages/ProjectDetail.jsx`

**State tillagt:**
```javascript
const [sources, setSources] = useState([])
const [showAddSourceModal, setShowAddSourceModal] = useState(false)
const [addingSource, setAddingSource] = useState(false)
const [newSource, setNewSource] = useState({ title: '', type: 'link', comment: '' })
```

**Handlers tillagda:**
- `handleAddSource()` - Skapa källa
- `handleDeleteSource()` - Ta bort källa (med bekräftelse)
- `getSourceTypeLabel()` - Översätt typ till svensk text

**UI komponenter:**
- Källor-sektion i context panel (höger kolumn)
- Lista med källor (typ-badge, titel, kommentar, datum)
- "Lägg till källa" modal med formulär
- Ta bort-knapp (×) per källa

### 6. Styling: `apps/web/src/pages/ProjectDetail.css`

**CSS classes tillagda:**
- `.context-header` - Header med titel + knapp
- `.btn-add-source` - "Lägg till källa" knapp
- `.sources-empty` - Tom-state text
- `.sources-list` - Lista med källor
- `.source-item` - Enskild källa i listan
- `.source-header` - Header per källa (typ-badge + delete-knapp)
- `.source-type-badge` - Badge för källtyp
- `.source-delete-btn` - Ta bort-knapp
- `.source-title` - Källans titel
- `.source-comment` - Kommentar (optional)
- `.source-date` - Skapad datum
- `.add-source-form` - Formulär i modal
- `.modal-actions` - Knappar i modal

---

## Verifiering

### Backend verification
```bash
docker compose exec api python _verify/verify_project_sources.py
```

**Resultat:** ✅ **7/7 PASS**

### Browser E2E

**Genomfört:**
1. ✅ Öppnat projekt i browser
2. ✅ Klickat "Lägg till källa" i Källor-sektionen
3. ✅ Fyllt i: Titel "Regeringens rapport", Typ "Länk", Kommentar "https://regeringen.se/rapport-2024"
4. ✅ Sparat → källa syns i listan
5. ✅ Refresh → källa finns kvar
6. ✅ Tagit bort "Expertintervju" (Person) via ×-knapp
7. ✅ Verifierat: endast en källa kvar
8. ✅ Öppnat Händelser → visar `source_added` och `source_removed`
9. ✅ Verifierat metadata: endast `type`, ingen titel/kommentar

**Status:** ✅ **PASS**

---

## Acceptance criteria

- [x] Backend: ProjectSource model + SourceType enum
- [x] API: POST, GET, DELETE endpoints
- [x] Events: source_added / source_removed (metadata: type only)
- [x] UI: Källor-sektion i context panel
- [x] UI: Modal för att lägga till källa
- [x] Verification: Backend script 7/7 PASS
- [x] Verification: Browser E2E PASS

---

## Filer som ändrades

1. `apps/api/models.py` - SourceType enum + ProjectSource model
2. `apps/api/schemas.py` - ProjectSourceCreate + ProjectSourceResponse
3. `apps/api/main.py` - POST, GET, DELETE endpoints
4. `apps/api/_verify/verify_project_sources.py` - Nytt verifieringsskript
5. `apps/web/src/pages/ProjectDetail.jsx` - Källor-sektion + modal + handlers
6. `apps/web/src/pages/ProjectDetail.css` - Styling

---

## Säkerhetsgarantier

- ✅ Källor lagras separat från innehåll
- ✅ Events via `_safe_event_metadata` (Privacy Guard enforcement)
- ✅ **ALDRIG** titel/kommentar/URL i events (endast `type`)
- ✅ Hard delete (CASCADE via foreign key)
- ✅ Ingen AI, ingen auto-fetch, ingen analys

---

## Slutsats

**Byggsten B: Källor / Referenser** är fullständigt implementerad och verifierad. All funktionalitet fungerar som specificerat, säkerhetsgarantier är på plats, och både backend och frontend E2E-tester är godkända utan undantag.

**Implementation:** ✅ Completed  
**Verification:** ✅ 7/7 Backend PASS, Browser E2E PASS  
**Security:** ✅ Privacy Guard enforcement verified

