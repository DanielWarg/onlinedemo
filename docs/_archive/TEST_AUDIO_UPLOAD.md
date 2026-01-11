ARCHIVED: replaced by docs/ARCHITECTURE.md, docs/FLOWS.md, docs/VERIFYING.md

# Test Audio Upload - Backend Direct Test

## STEG 1 - Endpoint Information

**Method:** POST  
**Path:** `/api/projects/{project_id}/recordings`  
**Multipart field:** `file` (UploadFile)  
**Auth:** Basic Auth (admin:password)  
**Content-Type:** multipart/form-data

### Flöde (steg-för-steg):

1. ✅ Verifiera projekt finns
2. ✅ Validera filstorlek (max 25MB)
3. ✅ Spara audio-fil till `uploads/{audio_file_id}{ext}`
4. ✅ Kör `transcribe_audio()` - lokal STT med openai-whisper
5. ✅ Kör `process_transcript()` - strukturera till markdown
6. ✅ Normalisera text
7. ✅ Progressive sanitization (normal → strict → paranoid)
8. ✅ Skapa dokument i DB
9. ✅ Skapa event `recording_transcribed` (endast metadata)
10. ✅ Returnera `DocumentListResponse` (metadata only)

## STEG 2 - Test med CURL

**Krav:** Ha en riktig ljudfil (mp3/wav/webm/ogg) redo.

### Exempel-kommando:

```bash
# Använd ett existerande projekt-ID (t.ex. 1)
PROJECT_ID=1
AUDIO_FILE="/path/to/your/real_audio.wav"

curl -v -X POST \
  http://localhost:8000/api/projects/${PROJECT_ID}/recordings \
  -u admin:password \
  -F "file=@${AUDIO_FILE}"
```

### Förväntat response (201 Created):

```json
{
  "id": 123,
  "project_id": 1,
  "filename": "röstmemo-20250101-120000.txt",
  "file_type": "txt",
  "classification": "normal",
  "sanitize_level": "normal",
  "usage_restrictions": {"ai_allowed": true, "export_allowed": true},
  "pii_gate_reasons": null,
  "created_at": "2025-01-01T12:00:00"
}
```

## STEG 3 - Loggning

Backend loggar nu (metadata-only):

- `[AUDIO] Audio file received: filename=X, size=Y bytes, mime=Z`
- `[AUDIO] Audio file saved: /path/to/file`
- `[AUDIO] Starting transcription...`
- `[AUDIO] Transcription finished: transcript_length=X chars`
- `[AUDIO] Creating document...`
- `[AUDIO] Document created with id=X`

**Viktigt:** Inget raw transcript loggas.

## STEG 4 - Verifiering

Efter curl-test, verifiera:

1. **Response status:** 201 Created
2. **Dokument skapas:** Kolla DB eller API `/api/projects/{id}/documents`
3. **Event skapas:** Kolla `/api/projects/{id}/events` för `recording_transcribed`
4. **Transcript är riktig:** Öppna dokumentet och verifiera att texten matchar ljudet

## Felsökning

Om curl:
- **Inte svarar:** Kolla API-loggarna för var processen blockerar
- **Svarar med error:** Kolla full traceback i loggarna
- **Svarar OK men inget dokument:** Kolla DB-query eller create-fail i loggarna

