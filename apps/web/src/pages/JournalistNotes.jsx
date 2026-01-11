import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { FileText, Plus, AlertCircle, HelpCircle, AlertTriangle, Image as ImageIcon, X, Edit, Trash2 } from 'lucide-react'
import { apiUrl } from '../lib/api'
import './JournalistNotes.css'

function JournalistNotes({ projectId }) {
  const [notes, setNotes] = useState([])
  const [activeNoteId, setActiveNoteId] = useState(null)
  const [activeNote, setActiveNote] = useState(null)
  const [noteTitle, setNoteTitle] = useState('')
  const [noteBody, setNoteBody] = useState('')
  const [noteCategory, setNoteCategory] = useState('raw')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState(null) // 'saving', 'saved', 'error'
  const [images, setImages] = useState([])
  const [imageUrls, setImageUrls] = useState({}) // Map image_id -> blob URL
  const [selectedImage, setSelectedImage] = useState(null)
  const [pasteFeedback, setPasteFeedback] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)
  
  const categoryOptions = [
    { value: 'raw', label: 'Råanteckning' },
    { value: 'work', label: 'Arbetsanteckning' },
    { value: 'reflection', label: 'Reflektion' },
    { value: 'question', label: 'Fråga' },
    { value: 'source', label: 'Källa' },
    { value: 'other', label: 'Övrigt' }
  ]
  
  const textareaRef = useRef(null)
  const imageInputRef = useRef(null)
  const saveTimeoutRef = useRef(null)

  const username = 'admin'
  const password = 'password'
  const auth = btoa(`${username}:${password}`)

  // Fetch notes list
  const fetchNotes = useCallback(async () => {
    try {
      const response = await fetch(apiUrl(`/projects/${projectId}/journalist-notes`), {
        headers: { 'Authorization': `Basic ${auth}` },
        credentials: 'omit'
      })
      if (!response.ok) throw new Error('Kunde inte hämta anteckningar')
      const data = await response.json()
      setNotes(data)
      
      // Only auto-select first note if no note is currently active
      // Don't change selection if user has explicitly selected a note
      if (!activeNoteId && data.length > 0) {
        setActiveNoteId(data[0].id)
      }
    } catch (err) {
      console.error('Error fetching notes:', err)
    } finally {
      setLoading(false)
    }
  }, [projectId, auth]) // Removed activeNoteId from dependencies to avoid loop

  // Fetch single note with body
  const fetchNote = useCallback(async (noteId) => {
    try {
      // Cleanup old blob URLs
      setImageUrls(prevUrls => {
        Object.values(prevUrls).forEach(url => {
          if (url && url.startsWith('blob:')) {
            URL.revokeObjectURL(url)
          }
        })
        return {}
      })
      
      const [noteResponse, imagesResponse] = await Promise.all([
        fetch(apiUrl(`/journalist-notes/${noteId}`), {
          headers: { 'Authorization': `Basic ${auth}` },
          credentials: 'omit'
        }),
        fetch(apiUrl(`/journalist-notes/${noteId}/images`), {
          headers: { 'Authorization': `Basic ${auth}` },
          credentials: 'omit'
        })
      ])
      
      if (!noteResponse.ok) throw new Error('Kunde inte hämta anteckning')
      const noteData = await noteResponse.json()
      setActiveNote(noteData)
      setNoteTitle(noteData.title || '')
      setNoteBody(noteData.body || '')
      setNoteCategory(noteData.category || 'raw')
      
      // Fetch images
      if (imagesResponse.ok) {
        const imagesData = await imagesResponse.json()
        setImages(imagesData)
        
        // Load images with auth and create blob URLs
        const urlMap = {}
        for (const image of imagesData) {
          try {
            const imgResponse = await fetch(apiUrl(`/journalist-notes/${noteId}/images/${image.id}`), {
              headers: { 'Authorization': `Basic ${auth}` },
              credentials: 'omit'
            })
            if (imgResponse.ok) {
              const blob = await imgResponse.blob()
              urlMap[image.id] = URL.createObjectURL(blob)
            }
          } catch (err) {
            console.error(`Error loading image ${image.id}:`, err)
          }
        }
        setImageUrls(urlMap)
      } else {
        setImages([])
        setImageUrls({})
      }
    } catch (err) {
      console.error('Error fetching note:', err)
    }
  }, [auth])

  useEffect(() => {
    fetchNotes()
  }, [fetchNotes])


  useEffect(() => {
    if (activeNoteId) {
      fetchNote(activeNoteId)
    } else {
      setActiveNote(null)
      setNoteTitle('')
      setNoteBody('')
      setNoteCategory('raw')
      setImages([])
      setImageUrls({})
    }
    
  }, [activeNoteId, fetchNote])
  
  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      setImageUrls(prevUrls => {
        Object.values(prevUrls).forEach(url => {
          if (url && url.startsWith('blob:')) {
            URL.revokeObjectURL(url)
          }
        })
        return {}
      })
    }
  }, [])

  // Autosave removed - manual save only

  const saveNote = async () => {
    if (!activeNoteId) return
    
    setSaving(true)
    setSaveStatus('saving')
    
    try {
      const response = await fetch(apiUrl(`/journalist-notes/${activeNoteId}`), {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          title: noteTitle || null,
          body: noteBody,
          category: noteCategory
        }),
        credentials: 'omit' // Prevent browser from showing native auth popup
      })
      
      if (!response.ok) throw new Error('Kunde inte spara anteckning')
      
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus(null), 3000)
      
      // Refresh notes list to update preview (but preserve activeNoteId)
      const currentActiveId = activeNoteId
      await fetchNotes()
      // Ensure activeNoteId is preserved after refresh
      if (currentActiveId) {
        setActiveNoteId(currentActiveId)
      }
      // Refresh note to get updated timestamp
      await fetchNote(activeNoteId)
      
      // Skapa dokument från anteckningen
      try {
        const documentText = noteTitle ? `${noteTitle}\n\n${noteBody}` : noteBody
        const blob = new Blob([documentText], { type: 'text/plain' })
        const filename = noteTitle ? `${noteTitle}.txt` : `anteckning-${new Date().toISOString().split('T')[0]}.txt`
        const file = new File([blob], filename, { type: 'text/plain' })
        
        const formData = new FormData()
        formData.append('file', file)
        
        await fetch(apiUrl(`/projects/${projectId}/documents`), {
          method: 'POST',
          headers: {
            'Authorization': `Basic ${auth}`
          },
          body: formData,
          credentials: 'omit'
        })
      } catch (docErr) {
        console.error('Error creating document from note:', docErr)
        // Fortsätt även om dokument-skapandet misslyckas
      }
    } catch (err) {
      console.error('Error saving note:', err)
      setSaveStatus('error')
      setTimeout(() => setSaveStatus(null), 3000)
    } finally {
      setSaving(false)
    }
  }

  const createNote = async () => {
    try {
      const response = await fetch(apiUrl(`/projects/${projectId}/journalist-notes`), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          title: null,
          body: '',
          category: 'raw'
        }),
        credentials: 'omit' // Prevent browser from showing native auth popup
      })
      
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Autentisering misslyckades. Kontrollera dina inloggningsuppgifter.')
        }
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Kunde inte skapa anteckning')
      }
      
      const newNote = await response.json()
      setActiveNoteId(newNote.id)
      await fetchNotes()
      // Öppna redigeringsläget direkt för ny anteckning
      await fetchNote(newNote.id)
      setShowEditModal(true)
    } catch (err) {
      console.error('Error creating note:', err)
      alert(err.message || 'Kunde inte skapa anteckning')
    }
  }

  const handleDeleteNote = (noteId, noteTitle) => {
    setDeleteTarget({ id: noteId, title: noteTitle || 'Ingen titel' })
    setShowDeleteConfirm(true)
  }

  const confirmDeleteNote = async () => {
    if (!deleteTarget) return
    
    setDeleting(true)
    let success = false
    
    try {
      const response = await fetch(apiUrl(`/journalist-notes/${deleteTarget.id}`), {
        method: 'DELETE',
        headers: {
          'Authorization': `Basic ${auth}`
        },
        credentials: 'omit'
      })
      
      // 204 No Content is success, don't try to parse body
      if (!response.ok && response.status !== 204) {
        throw new Error(`Failed to delete note: ${response.status}`)
      }
      
      success = true
      
      // If we deleted the active note, clear selection
      if (activeNoteId === deleteTarget.id) {
        setActiveNoteId(null)
        setActiveNote(null)
      }
      
      // Close modal
      setShowDeleteConfirm(false)
      setDeleteTarget(null)
      setDeleting(false)
      
      // Refresh notes list
      await fetchNotes()
    } catch (err) {
      console.error('Error deleting note:', err)
      alert('Kunde inte radera anteckning: ' + err.message)
    } finally {
      // Only reset deleting state if delete failed
      if (!success) {
        setDeleting(false)
      }
    }
  }

  const handlePaste = (e) => {
    e.preventDefault()
    
    // Get plain text from clipboard
    const pastedText = e.clipboardData.getData('text/plain')
    
    // Check for images in clipboard
    const items = Array.from(e.clipboardData.items)
    const imageItem = items.find(item => item.type.startsWith('image/'))
    
    if (imageItem) {
      // Handle image paste
      const file = imageItem.getAsFile()
      if (file && activeNoteId) {
        uploadImage(file)
      }
    } else if (pastedText) {
      // Handle text paste
      const textarea = textareaRef.current
      if (!textarea) return
      
      const start = textarea.selectionStart
      const end = textarea.selectionEnd
      const text = noteBody
      
      const newText = text.substring(0, start) + pastedText + text.substring(end)
      setNoteBody(newText)
      
      // Set cursor position after pasted text
      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = start + pastedText.length
        textarea.focus()
      }, 0)
      
      // Show visual feedback
      setPasteFeedback(true)
      setTimeout(() => setPasteFeedback(false), 500)
    }
  }

  const insertPrefix = (prefix) => {
    const textarea = textareaRef.current
    if (!textarea) return
    
    const start = textarea.selectionStart
    const text = noteBody
    const lineStart = text.lastIndexOf('\n', start - 1) + 1
    const lineEnd = text.indexOf('\n', start)
    const lineEndPos = lineEnd === -1 ? text.length : lineEnd
    
    const currentLine = text.substring(lineStart, lineEndPos)
    const newLine = currentLine.startsWith(prefix) 
      ? currentLine.substring(prefix.length).trim()
      : `${prefix} ${currentLine.trim()}`
    
    const newText = text.substring(0, lineStart) + newLine + text.substring(lineEndPos)
    setNoteBody(newText)
    
    // Set cursor position
    setTimeout(() => {
      const newPos = lineStart + newLine.length
      textarea.selectionStart = textarea.selectionEnd = newPos
      textarea.focus()
    }, 0)
  }

  const handleImageSelect = (e) => {
    const file = e.target.files?.[0]
    if (file && activeNoteId) {
      uploadImage(file)
    }
    // Reset input
    if (imageInputRef.current) {
      imageInputRef.current.value = ''
    }
  }

  const uploadImage = async (file) => {
    if (!activeNoteId) return
    
    // Validate file size (10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('Bilden är för stor. Maximal storlek är 10MB')
      return
    }
    
    // Validate image type
    if (!file.type.startsWith('image/')) {
      alert('Filen måste vara en bild')
      return
    }
    
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await fetch(apiUrl(`/journalist-notes/${activeNoteId}/images`), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`
        },
        body: formData,
        credentials: 'omit' // Prevent browser from showing native auth popup
      })
      
      if (!response.ok) throw new Error('Failed to upload image')
      
      const imageData = await response.json()
      
      // Visa bilden direkt i edit modal
      const imgResponse = await fetch(apiUrl(`/journalist-notes/${activeNoteId}/images/${imageData.id}`), {
        headers: { 'Authorization': `Basic ${auth}` },
        credentials: 'omit'
      })
      if (imgResponse.ok) {
        const blob = await imgResponse.blob()
        const newImageUrl = URL.createObjectURL(blob)
        setImageUrls(prev => ({ ...prev, [imageData.id]: newImageUrl }))
        setImages(prev => [...prev, imageData])
      }
      
      // Refresh note to get updated images list
      await fetchNote(activeNoteId)
      
      // Also refresh notes list to update preview
      await fetchNotes()
    } catch (err) {
      console.error('Error uploading image:', err)
      alert('Kunde inte ladda upp bild: ' + err.message)
    }
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('sv-SE', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (loading) {
    return <div className="journalist-notes-page">Laddar...</div>
  }

  return (
    <div className="journalist-notes-page">
      <div className="journalist-notes-layout">
        {/* Left Column: Notes List */}
        <div className="notes-list-column">
          <div className="notes-list-header">
            <h3 className="notes-list-title">Anteckningar</h3>
            <button
              className="btn-create-note"
              onClick={createNote}
              title="Skapa ny anteckning"
            >
              <Plus size={16} />
            </button>
          </div>
          
          <div className="notes-list">
            {notes.length === 0 ? (
              <div className="notes-empty">
                <p>Inga anteckningar ännu</p>
              </div>
            ) : (
              notes.map(note => (
                <div
                  key={note.id}
                  className={`note-item ${activeNoteId === note.id ? 'active' : ''}`}
                  onClick={() => setActiveNoteId(note.id)}
                >
                  <div className="note-item-header">
                    {note.title && (
                      <div className="note-item-title">{note.title}</div>
                    )}
                    <div className="note-item-preview">
                      {note.preview || '(Tom anteckning)'}
                    </div>
                  </div>
                  <div className="note-item-meta">
                    <span className="note-item-category">{categoryOptions.find(c => c.value === note.category)?.label || note.category}</span>
                    <span className="note-item-date">{formatDate(note.updated_at || note.created_at)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Column: Read View */}
        <div className="notes-editor-column">
          {activeNote ? (
            <>
              {/* Read-only view header with fixed height */}
              <div className="note-read-header">
                <div className="note-read-header-top">
                  <div className="note-read-title-section">
                    {noteTitle ? (
                      <h3 className="note-read-title">{noteTitle}</h3>
                    ) : (
                      <h3 className="note-read-title note-read-title-empty">Ingen titel</h3>
                    )}
                    <span className="note-read-category">
                      {categoryOptions.find(c => c.value === noteCategory)?.label || noteCategory}
                    </span>
                  </div>
                  <div className="note-read-actions">
                    <button
                      className="btn-edit-note"
                      onClick={() => setShowEditModal(true)}
                      title="Redigera anteckning"
                    >
                      <Edit size={16} />
                      <span>Redigera</span>
                    </button>
                    <button
                      className="btn-delete-note"
                      onClick={() => handleDeleteNote(activeNote.id, noteTitle)}
                      title="Radera anteckning"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
                {/* Fixed height meta row - prevents layout jump */}
                <div className="note-read-meta">
                  <span className="note-read-date">
                    Uppdaterad: {formatDate(activeNote.updated_at)}
                  </span>
                </div>
              </div>

              {/* Read-only body */}
              <div className="note-read-body">
                {noteBody ? (
                  <pre className="note-read-text">{noteBody}</pre>
                ) : (
                  <p className="note-read-empty">Ingen text ännu. Klicka "Redigera" för att lägga till innehåll.</p>
                )}
                
                {/* Display images inline */}
                {images.length > 0 && (
                  <div className="note-read-images">
                    <p className="note-read-images-label">Bilder i anteckningen:</p>
                    <div className="note-read-images-grid">
                      {images.map(image => (
                        <div key={image.id} className="note-read-image-item">
                          {imageUrls[image.id] ? (
                            <img
                              src={imageUrls[image.id]}
                              alt={image.filename}
                              className="note-read-image-thumb"
                              onClick={() => setSelectedImage(image)}
                            />
                          ) : (
                            <div className="note-read-image-thumb note-read-image-loading">
                              Laddar...
                            </div>
                          )}
                          <p className="note-read-image-filename">{image.filename}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="note-read-footer">
                <p className="note-read-footer-text">
                  Anteckningar är interna arbetsanteckningar och bearbetas inte automatiskt.
                </p>
              </div>
            </>
          ) : (
            <>
              {/* Collapsed preview - shows when no note is active but notes exist */}
              {notes.length > 0 && (
                <div className="editor-collapsed-preview">
                  <div className="collapsed-preview-header">
                    <h4 className="collapsed-preview-title">Anteckningar</h4>
                    <button 
                      className="btn-expand-notes"
                      onClick={() => {
                        // Select the most recently updated note
                        if (notes.length > 0) {
                          setActiveNoteId(notes[0].id)
                        }
                      }}
                      title="Visa anteckningar"
                    >
                      <FileText size={16} />
                    </button>
                  </div>
                  <div className="collapsed-preview-list">
                    {notes.slice(0, 3).map(note => (
                      <div
                        key={note.id}
                        className="collapsed-preview-item"
                        onClick={() => setActiveNoteId(note.id)}
                      >
                        <div className="collapsed-preview-item-title">
                          {note.title || note.preview || '(Tom anteckning)'}
                        </div>
                        <div className="collapsed-preview-item-meta">
                          {formatDate(note.updated_at || note.created_at)}
                        </div>
                      </div>
                    ))}
                    {notes.length > 3 && (
                      <div className="collapsed-preview-more">
                        +{notes.length - 3} fler...
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Empty state - shows when no notes exist */}
              {notes.length === 0 && (
                <div className="editor-empty">
                  <FileText size={48} className="editor-empty-icon" />
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Edit Modal - toolbar only in modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        title="Redigera anteckning"
      >
        <div className="edit-modal-content">
          {/* Fixed height status bar - prevents layout jump */}
          <div className="edit-modal-status-bar">
          </div>

          <div className="edit-modal-title-section">
            <input
              type="text"
              className="edit-modal-title-input"
              placeholder="Titel på anteckningen (valfritt)"
              value={noteTitle}
              onChange={(e) => setNoteTitle(e.target.value)}
            />
            <select
              className="edit-modal-category-select"
              value={noteCategory}
              onChange={(e) => setNoteCategory(e.target.value)}
            >
              {categoryOptions.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="edit-modal-toolbar">
            <button
              className="btn-prefix"
              onClick={() => insertPrefix('❗')}
              title="Viktigt"
            >
              <AlertCircle size={14} />
              <span>Viktigt</span>
            </button>
            <button
              className="btn-prefix"
              onClick={() => insertPrefix('❓')}
              title="Fråga"
            >
              <HelpCircle size={14} />
              <span>Fråga</span>
            </button>
            <button
              className="btn-prefix"
              onClick={() => insertPrefix('⚠️')}
              title="Osäkert"
            >
              <AlertTriangle size={14} />
              <span>Osäkert</span>
            </button>
            <input
              ref={imageInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageSelect}
              // Some browsers are picky about programmatic click() on display:none inputs.
              // Keep it visually hidden but present in the layout tree.
              style={{
                position: 'absolute',
                left: '-9999px',
                width: '1px',
                height: '1px',
                opacity: 0
              }}
            />
            <button
              className="btn-prefix"
              onClick={() => {
                try {
                  imageInputRef.current?.showPicker?.()
                } catch {
                  // ignore
                }
                imageInputRef.current?.click()
              }}
              title="Ladda upp bild"
            >
              <ImageIcon size={14} />
              <span>Bild</span>
            </button>
          </div>

          <div className={`edit-modal-textarea-container ${pasteFeedback ? 'paste-feedback' : ''}`}>
            <textarea
              ref={textareaRef}
              className="edit-modal-textarea"
              value={noteBody}
              onChange={(e) => setNoteBody(e.target.value)}
              onPaste={handlePaste}
              placeholder="Skriv anteckningar här..."
            />
          </div>

          {/* Visa bilder direkt i edit modal */}
          {images.length > 0 && (
            <div className="edit-modal-images">
              <p className="edit-modal-images-label">Bilder i anteckningen:</p>
              <div className="edit-modal-images-grid">
                {images.map(image => (
                  <div key={image.id} className="edit-modal-image-item">
                    {imageUrls[image.id] ? (
                      <img
                        src={imageUrls[image.id]}
                        alt={image.filename}
                        className="edit-modal-image-thumb"
                        onClick={() => setSelectedImage(image)}
                      />
                    ) : (
                      <div className="edit-modal-image-thumb edit-modal-image-loading">
                        Laddar...
                      </div>
                    )}
                    <p className="edit-modal-image-filename">{image.filename}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="edit-modal-footer">
            <div className="edit-modal-footer-left">
              {saveStatus && (
                <span className={`save-status save-status-${saveStatus}`}>
                  {saveStatus === 'saving' && '⏳ Sparas...'}
                  {saveStatus === 'saved' && '✓ Sparad'}
                  {saveStatus === 'error' && '✗ Fel vid sparande'}
                </span>
              )}
            </div>
            <div className="edit-modal-footer-right">
              <button
                className="btn-save-note"
                onClick={saveNote}
                disabled={saving}
              >
                {saving ? 'Sparar...' : 'Spara'}
              </button>
              <button
                className="btn-close-edit"
                onClick={() => setShowEditModal(false)}
              >
                Stäng
              </button>
            </div>
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal 
        isOpen={showDeleteConfirm} 
        onClose={() => !deleting && setShowDeleteConfirm(false)}
      >
        <div className="delete-confirmation-modal">
          <div className="delete-confirmation-icon">
            <Trash2 size={48} />
          </div>
          <h3 className="delete-confirmation-title">
            Radera anteckning?
          </h3>
          <p className="delete-confirmation-text">
            Är du säker på att du vill radera <strong>{deleteTarget?.title}</strong>?
          </p>
          <p className="delete-confirmation-warning">
            Denna åtgärd kan inte ångras.
          </p>
          <div className="delete-confirmation-actions">
            <button 
              className="btn-cancel-delete"
              onClick={() => setShowDeleteConfirm(false)}
              disabled={deleting}
            >
              Avbryt
            </button>
            <button 
              className="btn-confirm-delete"
              onClick={confirmDeleteNote}
              disabled={deleting}
            >
              {deleting ? 'Raderar...' : 'Radera permanent'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Image Modal */}
      {selectedImage && (
        <Modal
          isOpen={!!selectedImage}
          onClose={() => setSelectedImage(null)}
          title="Bild"
        >
          <div className="image-modal-content">
            {imageUrls[selectedImage.id] ? (
              <img 
                src={imageUrls[selectedImage.id]}
                alt={selectedImage.filename}
                className="image-modal-img"
              />
            ) : (
              <div className="image-modal-loading">Laddar bild...</div>
            )}
            <p className="image-modal-filename">{selectedImage.filename}</p>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default JournalistNotes

