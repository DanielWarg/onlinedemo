# Flöden

## Dokument-upload och sanering

```
Upload → Validate → Extract Text → Normalize → Mask → PII Gate → Save
  │         │            │             │          │        │         │
  │         │            │             │          │        │         └─> Document (maskerad vy)
  │         │            │             │          │        └─> FAIL om PII kvar
  │         │            │             │          └─> Maskerad text
  │         │            │             └─> Normaliserad text
  │         │            └─> Råtext (PDF/TXT)
  │         └─> Filtyp + storlek check
  └─> PDF/TXT fil
```

## Röstmemo-transkribering

```
Audio Upload → Save File → STT Engine → Normalize → Refine Editorial → Create Document
     │            │            │            │              │                  │
     │            │            │            │              │                  └─> Document (maskerad vy)
     │            │            │            │              └─> Redaktionell förädling
     │            │            │            └─> Normaliserat transkript
     │            │            └─> Råtranskript (aldrig loggat)
     │            └─> Permanent lagring
     └─> MP3/WAV fil
```

## Fort Knox Compile Pipeline

```
POST /api/fortknox/compile
  │
  ├─> 1. Build KnoxInputPack
  │     ├─> Collect Documents (text + metadata)
  │     ├─> Collect Notes (text + metadata)
  │     ├─> Collect Sources (metadata only)
  │     └─> Generate Fingerprint
  │
  ├─> 2. Input Gate
  │     ├─> Sanitize Level Check
  │     ├─> PII Gate Check
  │     └─> Size Check
  │     └─> FAIL → INPUT_GATE_FAILED
  │
  ├─> 3. Idempotens Check
  │     ├─> Lookup by Fingerprint
  │     └─> Match → Return Existing Report
  │
  ├─> 4. Remote URL Check
  │     ├─> FORTKNOX_REMOTE_URL exists?
  │     └─> No → FORTKNOX_OFFLINE (men idempotens fungerar)
  │
  ├─> 5. Remote Call
  │     ├─> Test Mode → Use Fixtures
  │     └─> Production → Call Remote Service
  │
  ├─> 6. Output Gate + Re-ID Guard
  │     ├─> PII Gate Check
  │     └─> Re-ID Guard Check
  │     └─> FAIL → OUTPUT_GATE_FAILED
  │
  └─> 7. Save KnoxReport
        └─> Return Report (201 Created)
```

## Feed Import Flow

```
POST /api/projects/from-feed
  │
  ├─> 1. Preview Feed (optional)
  │     └─> GET /api/feeds/preview?url=...
  │
  ├─> 2. Create Project
  │     └─> Project with feed metadata
  │
  ├─> 3. For each Feed Item:
  │     ├─> Extract Fulltext (trafilatura)
  │     ├─> Create Document (from fulltext)
  │     ├─> Create ProjectNote (structured)
  │     ├─> Create ProjectSource (URL + metadata)
  │     └─> Deduplication Check (GUID/link)
  │
  └─> 4. Return Project with all items
```

## Verify Loop (Fort Knox)

```
make verify-fortknox-v1-loop
  │
  ├─> Attempt 1/N
  │     ├─> Run verify_fortknox_v1.py
  │     ├─> Exit 0 → PASS ✅
  │     ├─> Exit 100 → NEEDS_RESTART
  │     │     ├─> Read /tmp/fortknox_compose_update_needed
  │     │     ├─> Copy compose from container
  │     │     ├─> Restart API
  │     │     ├─> Wait for /health
  │     │     └─> Continue loop
  │     └─> Exit 1+ → FAIL ❌
  │
  └─> Max attempts → FAIL
```

## State Machine (Test 5)

```
Start → No Flags
  │
  ├─> Create Project + Doc + Note
  ├─> Set FORTKNOX_REMOTE_URL = ""
  ├─> Create t5_5a_done.flag
  └─> Exit 100 (restart)

After Restart → t5_5a_done exists
  │
  ├─> Restore FORTKNOX_REMOTE_URL
  ├─> Create t5_waiting_for_remote_restore.flag
  └─> Exit 100 (restart)

After Restart → t5_waiting_for_remote_restore exists
  │
  ├─> Health Check (/api/health)
  ├─> Create t5_remote_restored_for_5b.flag
  ├─> Compile Report (online)
  ├─> Create t5_report_created.flag
  ├─> Set FORTKNOX_REMOTE_URL = "" again
  ├─> Create t5_remote_restored.flag
  └─> Exit 100 (restart)

After Restart → t5_remote_restored exists
  │
  ├─> Test Idempotency (offline)
  ├─> Create t5_done.flag
  └─> PASS ✅
```
