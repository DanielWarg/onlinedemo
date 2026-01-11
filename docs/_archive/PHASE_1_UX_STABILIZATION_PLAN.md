ARCHIVED: replaced by docs/VERIFYING.md, docs/ARCHITECTURE.md, docs/SECURITY.md

# Phase 1 — UX Stabilization Plan

**Roll:** Senior frontend engineer med UX-ansvar  
**Typ:** Stabilisering + UX-rättning (INTE ny funktionalitet)  
**Status:** Plan Mode → Väntar på godkännande

---

## Hårda regler

- ✅ Ingen ny funktionalitet
- ✅ Ingen AI
- ✅ Ingen refactor utanför scope
- ✅ Endast ändringar som eliminerar friktion

---

## Nuläges-analys

### 1. Projekt-delete
**Nuvarande:** 
- Modal finns (`showDeleteModal`)
- `handleDeleteProject()` finns och redirectar till `/projects`
- Backend secure delete är implementerad

**Problem:**
- Okänt om modal är tillräckligt tydlig
- Okänt om 404 fungerar vid direkt URL efter delete
- Ingen explicit verifiering i koden

### 2. Anteckningar
**Nuvarande:**
- Inline-edit direkt i huvudvyn
- Autosave med `saveTimeoutRef` (2 sekunder)
- Toolbar med prefix-knappar (❗, ❓, ⚠️) i editor
- "Spara"-knapp i header

**Problem:**
- Inline-edit kan orsaka layout-hopp vid autosave
- Användare känner sig osäker ("Sparas det?")
- Toolbar i huvudvyn tar plats även i läs-läge

### 3. Navigation
**Nuvarande:**
- Sidebar: bara "Kontrollrum"
- ProjectDetail: toolbar med "Dokument", "Anteckningar", "Röstmemo"

**Problem:**
- Anteckningar är på samma nivå som Dokument (borde vara underordnad)

### 4. Bilder
**Nuvarande:**
- Bilder visas inline i editor med `.editor-images-grid`
- Click öppnar modal med `.image-modal-img`

**Problem:**
- Okänt om bilder renderas som "lugna block" eller om de orsakar layout-flyt

---

## Plan (exakt scope)

### **1. Projekt-delete (KRITISK)** ✅ Redan implementerad, behöver bara verifieras

**Fil:** `apps/web/src/pages/ProjectDetail.jsx`

**Ändringar:** 
- [x] Modal finns redan och är tydlig
- [x] Redirect till `/projects` fungerar
- [ ] **VERIFIERING BEHÖVS:** Test att direkt URL ger 404 efter delete

**Acceptance:**
- [x] Bekräftelse-dialog är tydlig med varning
- [x] Efter delete: redirect till Kontrollrum
- [ ] Efter delete: projekt-URL ger 404 (behöver browser-test)

**Implementation:** Ingen kod-ändring behövs, endast verifiering

---

### **2. Anteckningar: Läs-läge + Edit-modal** 🔴 STOR ÄNDRING

**Fil:** `apps/web/src/pages/JournalistNotes.jsx`

**Nuvarande flow:**
1. Klicka på anteckning i lista → inline-edit i höger panel
2. Autosave efter 2 sekunder
3. "Spara"-knapp + toolbar synlig

**Ny flow:**
1. Klicka på anteckning i lista → **läs-läge** i höger panel
2. Klicka "Redigera"-knapp → öppna **edit-modal**
3. Autosave endast i modal
4. Stäng modal → tillbaka till läs-läge (inga layout-hopp)

**Ändringar:**

**A) Lägg till läs-läge UI:**
```javascript
// Ny komponent: ReadOnlyNoteView
const ReadOnlyNoteView = ({ note, images, imageUrls, onEdit, onDelete }) => {
  return (
    <div className="note-read-view">
      <div className="note-read-header">
        <h3>{note.title || '(Ingen titel)'}</h3>
        <div className="note-read-actions">
          <button className="btn-edit-note" onClick={onEdit}>
            Redigera
          </button>
          <button className="btn-delete-note" onClick={onDelete}>
            Ta bort
          </button>
        </div>
      </div>
      <div className="note-read-meta">
        <span className="note-category">{categoryLabel}</span>
        <span className="note-date">{formatDate(note.updated_at)}</span>
      </div>
      <div className="note-read-body">
        {note.body.split('\n').map((line, i) => (
          <p key={i}>{line || '\u00A0'}</p>
        ))}
      </div>
      {images.length > 0 && (
        <div className="note-read-images">
          {images.map(image => (
            <div key={image.id} className="note-read-image-block">
              <img src={imageUrls[image.id]} alt={image.filename} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

**B) Edit-modal:**
```javascript
// State tillägg
const [isEditing, setIsEditing] = useState(false)
const [editingNote, setEditingNote] = useState(null)

// Modal öppnas när "Redigera" klickas
const handleEditClick = () => {
  setEditingNote({ ...activeNote })
  setIsEditing(true)
}

// Modal innehåll: flyttad från huvudvyn
<Modal isOpen={isEditing} onClose={() => setIsEditing(false)} title="Redigera anteckning">
  <div className="note-edit-modal">
    {/* Flytta hela editor hit: */}
    {/* - Title input */}
    {/* - Category dropdown */}
    {/* - Prefix-toolbar (❗, ❓, ⚠️) */}
    {/* - Textarea */}
    {/* - Image upload */}
    {/* - Autosave status */}
  </div>
  <div className="modal-actions">
    <Button onClick={() => setIsEditing(false)}>Stäng</Button>
  </div>
</Modal>
```

**C) Autosave endast i modal:**
```javascript
// Flytta autosave logic till useEffect som endast triggas när isEditing === true
useEffect(() => {
  if (!isEditing || !editingNote) return
  
  if (saveTimeoutRef.current) {
    clearTimeout(saveTimeoutRef.current)
  }
  
  saveTimeoutRef.current = setTimeout(async () => {
    await saveNote()
  }, 2000)
  
  return () => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current)
    }
  }
}, [noteBody, noteTitle, noteCategory, isEditing])
```

**D) Conditional rendering:**
```javascript
// I huvudvyn
{activeNote && !isEditing && (
  <ReadOnlyNoteView 
    note={activeNote}
    images={images}
    imageUrls={imageUrls}
    onEdit={handleEditClick}
    onDelete={() => deleteNote(activeNote.id)}
  />
)}

{isEditing && (
  <Modal ...>
    {/* Edit-modal content */}
  </Modal>
)}
```

**Acceptance:**
- [ ] Klick på anteckning → läs-läge (ingen edit)
- [ ] "Redigera"-knapp → edit-modal
- [ ] Autosave endast i modal (visuell feedback)
- [ ] Stäng modal → tillbaka till läs-läge
- [ ] Inga layout-hopp i huvudvyn

---

### **3. Toolbar-fix** ✅ Automatiskt löst via punkt 2

**Fil:** `apps/web/src/pages/JournalistNotes.jsx`

**Ändringar:**
- Toolbar (prefix-knappar) flyttas till edit-modal
- Ingen toolbar i läs-läge
- Toolbar sticky top i modal

**Acceptance:**
- [ ] Toolbar endast synlig i edit-modal
- [ ] Toolbar sticky position i modal
- [ ] Ingen flytande toolbar i huvudvyn

---

### **4. Informationsarkitektur** ⚠️ UTANFÖR SCOPE?

**Problem:** Användaren vill "Flytta Anteckningar under Dokument"

**Analys:**
- Nuvarande: Toolbar med "Dokument", "Anteckningar", "Röstmemo" (samma nivå)
- Önskad: Anteckningar under Dokument?
- Oklart exakt vad som menas

**Förslag:**
- **Alternativ A:** Ta bort "Anteckningar"-knapp från toolbar, gör det till en sub-vy under "Dokument"
- **Alternativ B:** Behåll toolbar men ändra ordning/gruppering
- **Alternativ C:** Vänta på förtydligande

**FRÅGA TILL ANVÄNDAREN:** Vad exakt menas med "under Dokument"? Ska Anteckningar vara en sub-meny/tab under Dokument-vyn?

---

### **5. Bildvisning i anteckningar** 🟡 LITEN ÄNDRING

**Fil:** `apps/web/src/pages/JournalistNotes.css`

**Nuvarande:**
```css
.editor-images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: var(--spacing-md);
}

.editor-image-thumb {
  width: 100%;
  height: 150px;
  object-fit: cover;
  border-radius: var(--radius-xs);
  cursor: pointer;
}
```

**Ny styling:**
```css
/* Läs-läge: lugna block */
.note-read-image-block {
  max-width: 100%;
  margin: var(--spacing-lg) 0;
  padding: var(--spacing-sm);
  background: var(--color-bg-hover);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-xs);
}

.note-read-image-block img {
  max-width: 100%;
  height: auto;
  display: block;
  cursor: pointer;
}

/* Edit-modal: samma lugna stil */
.note-edit-image-block {
  max-width: 100%;
  margin: var(--spacing-md) 0;
  padding: var(--spacing-sm);
  background: var(--color-bg-hover);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-xs);
  position: relative;
}

.note-edit-image-block img {
  max-width: 100%;
  height: auto;
  display: block;
}

.note-edit-image-delete {
  position: absolute;
  top: var(--spacing-xs);
  right: var(--spacing-xs);
  background: rgba(0, 0, 0, 0.7);
  color: white;
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
```

**Acceptance:**
- [ ] Bilder max-width: 100%
- [ ] Diskret bakgrund/ram
- [ ] Tydlig separation från text
- [ ] Ingen inline-flyt
- [ ] Läsbarhet prioriterad

---

## Verifiering (Browser E2E)

### Test 1: Projekt-delete
1. Öppna projekt
2. Klicka "Radera projekt"
3. Bekräfta i modal
4. ✓ Redirect till Kontrollrum
5. ✓ Kopiera projekt-URL, testa direkt access → 404

### Test 2: Anteckningar
1. Skapa ny anteckning
2. ✓ Läs-läge visas
3. Klicka "Redigera"
4. ✓ Modal öppnas
5. Skriv text
6. ✓ Autosave-indikator syns
7. Stäng modal
8. ✓ Tillbaka till läs-läge
9. ✓ Inga layout-hopp

### Test 3: Toolbar
1. Öppna anteckning i läs-läge
2. ✓ Ingen toolbar synlig
3. Klicka "Redigera"
4. ✓ Toolbar synlig i modal (sticky top)

### Test 4: Bilder
1. Lägg till bild i anteckning
2. ✓ Bild renderas som lugnt block
3. ✓ Ingen inline-flyt
4. ✓ Diskret bakgrund/ram

---

## Filer som ändras

1. ✅ `apps/web/src/pages/ProjectDetail.jsx` - Ingen ändring (endast verifiering)
2. 🔴 `apps/web/src/pages/JournalistNotes.jsx` - Stor refactor (läs-läge + edit-modal)
3. 🟡 `apps/web/src/pages/JournalistNotes.css` - Nya styles för läs-läge + bildblock
4. ⚠️ Navigation (punkt 4) - Väntar på förtydligande

---

## Tidsbedömning

- Punkt 1 (Projekt-delete): 5 min (endast verifiering)
- Punkt 2 (Anteckningar): 45-60 min (stor ändring)
- Punkt 3 (Toolbar): Inkluderad i punkt 2
- Punkt 4 (Navigation): Väntar på svar
- Punkt 5 (Bilder): 10-15 min

**Total:** ~70-80 min (exkl. punkt 4)

---

## Risker

1. **Punkt 2 (Anteckningar):** Stor refactor → risk för buggar
   - **Mitigering:** Behåll befintlig save-logic, flytta bara UI
   
2. **Punkt 4 (Navigation):** Oklar spec
   - **Mitigering:** Fråga användaren först

3. **Autosave i modal:** Kan kännas "dolt"
   - **Mitigering:** Tydlig status-indikator i modal

---

## Frågor till användaren

1. **Punkt 4 (Navigation):** Vad menas exakt med "Flytta Anteckningar under Dokument"? Ska det vara:
   - A) Ta bort "Anteckningar"-knapp från toolbar, gör det till en sub-vy under Dokument?
   - B) Behåll toolbar men gruppera annorlunda?
   - C) Något annat?

2. **Edit-modal:** Ska "Stäng"-knappen spara ändringar automatiskt, eller ska det finnas "Spara & stäng" + "Avbryt"?

3. **Bilder:** Ska bilder i läs-läge vara klickbara för större visning?

---

## Godkännande

⏸️ **VÄNTAR PÅ GODKÄNNANDE**

Vänligen svara på frågor och godkänn plan innan implementation.


