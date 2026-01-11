# Feed Import Implementation Plan

## IMPLEMENTED (Full Feed Import)

### Completed Features

#### 1. Model & Schema Changes
- ✅ **ProjectSource.url**: Added `url` field (first-class, nullable for backward compatibility)
- ✅ **ProjectNote.usage_restrictions**: Added `usage_restrictions` JSON field (same as Document)
- ✅ **Project.tags**: Verified exists (JSON field)
- ✅ **Schemas**: Updated `ProjectSourceResponse`, `CreateProjectFromFeedRequest` (with `mode`), `CreateProjectFromFeedResponse` (with `created_notes`, `created_sources`)

#### 2. Database Migrations (Idempotent)
- ✅ **project_sources.url**: Added via `init_db.sql` with idempotent check
- ✅ **project_notes.usage_restrictions**: Added via `init_db.sql` with idempotent check

#### 3. Fulltext Extraction
- ✅ **trafilatura**: Primary extraction library (with fallback to BeautifulSoup + html2text)
- ✅ **fetch_article_text()**: Implements fulltext extraction with SSRF protection
- ✅ **Fallback chain**: trafilatura → BeautifulSoup+html2text → simple text extraction → RSS summary

#### 4. Tag Derivation
- ✅ **derive_tags()**: Extracts tags from feed title/URL
  - Always includes "rss"
  - Includes "polisen" if found in title/URL
  - Extracts region from feed title (split on " – " or " - ", slug second part)
  - Example: "Polisen – Västra Götaland" → ["polisen", "västra-götaland", "rss"]

#### 5. Pipeline Reuse
- ✅ **run_sanitize_pipeline()**: Helper function that runs full pipeline (normalize → mask_text progressive → pii_gate_check)
- ✅ **Fail-closed**: If pipeline fails, item is skipped (no partial writes)
- ✅ **Same pipeline for Document and ProjectNote**: Both use identical sanitization

#### 6. Endpoints
- ✅ **GET /api/feeds/preview**: Preview feed without creating project
- ✅ **POST /api/projects/from-feed**: Full implementation with:
  - Project creation with description/tags
  - Document creation (with metadata)
  - ProjectSource creation (with URL, dedupe on URL)
  - ProjectNote creation (with masked_body, sanitize_level, usage_restrictions)
  - Fulltext extraction (mode="fulltext") or summary (mode="summary")
  - Idempotent deduplication (per project on item_guid or item_link)

#### 7. SSRF Protection
- ✅ **validate_and_fetch()**: Robust SSRF protection for both feed and article URLs
  - Only http/https allowed
  - DNS resolution + IP validation (blocks private IPs)
  - Redirect validation (max 3 redirects, validates each hop)
  - Timeout 10s, max 5MB

#### 8. Verification
- ✅ **verify_feed_project_full.py**: Comprehensive test script
  - Tests preview endpoint
  - Tests project creation with fulltext
  - Verifies database state (Project, Document, ProjectNote, ProjectSource)
  - Tests idempotency (re-import yields 0 new items)
- ✅ **Make target**: `make verify-feed-full`

#### 9. Edit Functionality
- ✅ **Document editing**: `PUT /api/documents/{document_id}` endpoint for updating document content
- ✅ **Note editing**: `PUT /api/projects/{project_id}/notes/{note_id}` endpoint for updating ProjectNote
- ✅ **Source editing**: `PUT /api/projects/{project_id}/sources/{source_id}` endpoint for updating ProjectSource
- ✅ **Frontend UI**: Edit buttons and modals in DocumentView and ProjectDetail
- ✅ **Pipeline re-run**: All edits go through same sanitization pipeline (normalize → mask → pii_gate_check)

#### 10. Filename Generation
- ✅ **Feed-based filenames**: Documents use feed item title as filename (sanitized for filesystem)
- ✅ **Scout-based filenames**: Scout items use item title as filename
- ✅ **Sanitization**: Special characters removed, spaces replaced with underscores, max 100 chars

#### 11. UI Improvements
- ✅ **Notes in sources section**: ProjectNotes displayed in same section as ProjectSources
- ✅ **Removed separate notes section**: No "Anteckningar (Feed)" section, all in "Källor"
- ✅ **Edit buttons**: Edit icons for documents, notes, and sources
- ✅ **Source URLs**: Clickable links for source URLs

#### 12. Files Changed
- `apps/api/models.py`: Added `ProjectSource.url`, `ProjectNote.usage_restrictions`
- `apps/api/schemas.py`: Updated feed-related schemas, added `DocumentUpdate`, `ProjectSourceUpdate`, `NoteUpdate`
- `apps/api/init_db.sql`: Added idempotent migrations
- `apps/api/feeds.py`: Added `fetch_article_text()`, `derive_tags()`, updated `validate_and_fetch()`
- `apps/api/main.py`: 
  - Added `run_sanitize_pipeline()` helper
  - Updated `create_project_from_feed` endpoint
  - Added `PUT /api/documents/{document_id}` for document editing
  - Added `PUT /api/projects/{project_id}/notes/{note_id}` for note editing
  - Added `PUT /api/projects/{project_id}/sources/{source_id}` for source editing
  - Updated filename generation to use feed item titles
- `apps/api/requirements.txt`: Added trafilatura, beautifulsoup4, html2text
- `apps/api/_verify/verify_feed_project_full.py`: New verification script
- `apps/web/src/pages/DocumentView.jsx`: Added edit functionality with modal
- `apps/web/src/pages/DocumentView.css`: Added styling for edit button
- `apps/web/src/pages/ProjectDetail.jsx`: 
  - Integrated ProjectNotes into sources section
  - Added edit functionality for notes and sources
  - Removed separate "Anteckningar (Feed)" section
- `apps/web/src/pages/ProjectDetail.css`: Added styling for edit buttons and source links
- `Makefile`: Added `verify-feed-full` target
- `tests/fixtures/sample.rss`: Test RSS fixture
- `tests/fixtures/sample_article.html`: Test article HTML fixture

---

# Feed Import Implementation Plan (Original)

## A) Inventory - Nuvarande System

### Projekt-skapande
- **Fil:** `apps/api/main.py:140-168`
- **Endpoint:** `POST /api/projects`
- **Schema:** `ProjectCreate` (från `schemas.py`)
- **Model:** `Project` (från `models.py`)

### Document Ingest Pipeline
- **Fil:** `apps/api/main.py:434-689` (`POST /api/projects/{project_id}/documents`)
- **Pipeline-steg:**
  1. Extract text (`extract_text_from_pdf` eller `extract_text_from_txt`)
  2. Normalize (`normalize_text` från `text_processing.py`)
  3. Progressive sanitization:
     - `mask_text(normalized_text, level="normal")`
     - `pii_gate_check(masked_text)`
     - Om fail → `mask_text(..., level="strict")`
     - Om fail → `mask_text(..., level="paranoid")`
  4. Spara `Document` med: `filename`, `file_type`, `masked_text`, `sanitize_level`, `pii_gate_reasons`, `usage_restrictions`

### PII Gate & Sanitization
- **Fil:** `apps/api/text_processing.py`
- **Funktioner:** `mask_text()`, `pii_gate_check()`, `normalize_text()`
- **Säkerhet:** Fail-closed princip

### Database Models
- **Fil:** `apps/api/models.py`
- **Project:** id, name, description, classification, status, due_date, tags (JSON)
- **Document:** id, project_id, filename, file_type, classification, masked_text, file_path, sanitize_level, usage_restrictions (JSON), pii_gate_reasons (JSON)
- **OBS:** Document saknar metadata-fält för feed info → måste läggas till

### Feed Parsing (befintlig)
- **Fil:** `apps/api/scout.py`
- **Bibliotek:** `feedparser` (redan i `requirements.txt`)
- **Användning:** RSS/Atom parsing med `feedparser.parse()`

### Frontend
- **Fil:** `apps/web/src/pages/CreateProject.jsx` - Modal för projekt-skapande
- **Fil:** `apps/web/src/pages/ProjectsList.jsx` - Lista projekt med "Nytt projekt" knapp

---

## Filer som skapas/ändras

**Backend:**
- `apps/api/feeds.py` (NY) - Feed fetching med SSRF-skydd, parsing, HTML-to-text
- `apps/api/models.py` - Lägg till `metadata` (JSON) i Document
- `apps/api/schemas.py` - Lägg till FeedPreviewResponse, FeedItemPreview, CreateProjectFromFeedRequest/Response
- `apps/api/main.py` - Lägg till GET /api/feeds/preview och POST /api/projects/from-feed

**Frontend:**
- `apps/web/src/pages/CreateProjectFromFeed.jsx` (NY) - Modal för feed import
- `apps/web/src/pages/ProjectsList.jsx` - Lägg till "Skapa projekt från feed" knapp

**Verifiering:**
- `apps/api/_verify/verify_feed_import.py` (NY) - Test script med fixture
- `tests/fixtures/sample.rss` (NY) - Test fixture

**Dokumentation:**
- `docs/FEED_IMPORT_PLAN.md` (denna fil)

---

## Säkerhetskrav

- **SSRF-skydd (ROBUST):**
  - Endast http/https tillåtna
  - DNS-resolve och validera resolved IP (blocka privata IP även efter DNS)
  - Blocka redirects till privata IP (följ redirects men validera varje hop)
  - Blocka: localhost, 127.0.0.1, privata IP-range, link-local
  - Timeout: 10s, Max storlek: 5MB

- **DB-migration:** Måste bevisas att Document.metadata läggs till korrekt (API får inte ge 500)

- **Dedupe:** guid prioriteras, annars link (per projekt)

- **Ingen ändring i PII-gate/sanitization:** Använd exakt samma pipeline som befintliga dokument

---

## Implementation Status

### Backend
- [x] **A) Inventory** - Dokumenterat nuvarande system
- [x] **B) Backend – feeds.py + preview** - Skapat `apps/api/feeds.py` med SSRF-skydd, parse_feed, html_to_text
- [x] **B) Backend – preview endpoint** - Lagt till `GET /api/feeds/preview` i `main.py`
- [x] **C) Backend – document metadata** - Lagt till `document_metadata` (JSON) i Document model
- [x] **C) Backend – create endpoint** - Lagt till `POST /api/projects/from-feed` med dedupe och ingest-pipeline
- [x] **C) Backend – DB migration** - Idempotent schema patch i `init_db.sql`

### Frontend
- [x] **D) Frontend – modal** - Skapat `CreateProjectFromFeed.jsx` med URL input, preview, limit selector
- [x] **D) Frontend – button** - Lagt till "Skapa projekt från feed" knapp i `ProjectsList.jsx`
- [x] **D) Frontend – Scout integration** - Lagt till "Skapa projekt" knapp i Scout modal feeds-tab

### Verifiering
- [x] **E) Verifiering – script** - Skapat `verify_feed_import.py` med fixture och dedupe-verifiering
- [x] **E) Verifiering – fixture** - Skapat `tests/fixtures/sample.rss`
- [x] **E) Verifiering – make target** - Lagt till `make verify-feed-import`
- [x] **E) Verifiering – körning** - Alla tester går grönt

### Status: ✅ KOMPLETT
