import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Lock, CheckCircle, XCircle, AlertCircle, Loader, AlertTriangle, FileText, StickyNote, Info, Edit } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Select } from '../ui/Select'
import { Modal } from '../ui/Modal'
import { apiUrl } from '../lib/api'
import { pollJob } from '../lib/jobs'
import './FortKnoxPanel.css'

function FortKnoxPanel({ projectId }) {
  const navigate = useNavigate()
  const [policyId, setPolicyId] = useState('internal')
  const [templateId, setTemplateId] = useState('weekly')
  const [loading, setLoading] = useState(false)
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)
  const [lastReportId, setLastReportId] = useState(null)
  const [isCacheHit, setIsCacheHit] = useState(false)
  const [savingReportDoc, setSavingReportDoc] = useState(false)
  const [savedReportDoc, setSavedReportDoc] = useState(null) // {id, filename}
  const [fixingItems, setFixingItems] = useState(new Set())
  const [fixedItems, setFixedItems] = useState(new Set())
  const [fixErrors, setFixErrors] = useState(new Map())
  const [deletingItems, setDeletingItems] = useState(new Set())
  const [showDocumentModal, setShowDocumentModal] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState(null)
  const [documentLoading, setDocumentLoading] = useState(false)
  const [autoCompileAfterExclude, setAutoCompileAfterExclude] = useState(false)
  const [showEditDocumentModal, setShowEditDocumentModal] = useState(false)
  const [editingDocument, setEditingDocument] = useState(null)
  const [editDocumentText, setEditDocumentText] = useState('')
  const [savingDocument, setSavingDocument] = useState(false)
  const [showNoteModal, setShowNoteModal] = useState(false)
  const [selectedNote, setSelectedNote] = useState(null)
  const [noteLoading, setNoteLoading] = useState(false)
  const [showEditNoteModal, setShowEditNoteModal] = useState(false)
  const [editingNote, setEditingNote] = useState(null)
  const [editNoteTitle, setEditNoteTitle] = useState('')
  const [editNoteBody, setEditNoteBody] = useState('')
  const [savingNote, setSavingNote] = useState(false)

  const parseKnoxError = (payload) => {
    // Handle Pydantic validation errors (422) - detail is a list
    if (Array.isArray(payload?.detail)) {
      const reasons = payload.detail.map(err => {
        const loc = err.loc ? err.loc.join('.') : 'unknown'
        const msg = err.msg || 'Validation error'
        return `${loc}: ${msg}`
      })
      return { error_code: 'VALIDATION_ERROR', reasons, detail: payload }
    }
    
    // Handle wrapped error (detail.error_code)
    if (payload?.detail?.error_code) {
      return payload.detail
    }
    
    // Handle direct error_code
    if (payload?.error_code) {
      return payload
    }
    
    // Fallback
    return { error_code: 'UNKNOWN', reasons: [JSON.stringify(payload)], detail: payload }
  }

  const getStatus = () => {
    if (loading) return 'WORKING'
    if (error) {
      const errorCode = error.error_code
      if (errorCode === 'FORTKNOX_OFFLINE') return 'OFFLINE'
      if (errorCode === 'INPUT_GATE_FAILED' || errorCode === 'OUTPUT_GATE_FAILED') return 'BLOCKED'
      if (errorCode === 'EMPTY_INPUT_SET') return 'ERROR'
      if (errorCode === 'VALIDATION_ERROR') return 'ERROR'
      if (error.reasons?.some(r => r.includes('quote_detected'))) return 'BLOCKED'
      return 'ERROR'
    }
    if (report) return 'PASS'
    return 'READY'
  }

  const status = getStatus()

  // Auto-compile after exclude
  useEffect(() => {
    if (autoCompileAfterExclude && !loading && deletingItems.size === 0 && fixingItems.size === 0) {
      // Reset flag first to prevent multiple triggers
      setAutoCompileAfterExclude(false)
      // Compile immediately since we've already checked conditions
      handleCompile()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoCompileAfterExclude, loading, deletingItems.size, fixingItems.size])

  // Auto-compile when all errors are fixed or items are excluded
  useEffect(() => {
    if (error && status === 'BLOCKED') {
      const blockedItems = parseBlockedReasons(error.reasons || [])
      
      // Check if all blocked items are either fixed or excluded
      // When items are excluded, they won't appear in blockedItems anymore after re-compile
      // So we need to check if there are any remaining blocked items
      const remainingDocs = blockedItems.documents.filter(doc => !fixedItems.has(`document_${doc.id}`))
      const remainingNotes = blockedItems.notes.filter(note => !fixedItems.has(`note_${note.id}`))
      
      // If no remaining blocked items and we're not currently loading or fixing, auto-compile
      if (remainingDocs.length === 0 && remainingNotes.length === 0 && !loading && fixingItems.size === 0 && deletingItems.size === 0) {
        // Small delay to ensure state is updated
        const timeoutId = setTimeout(() => {
          handleCompile()
        }, 1000)
        return () => clearTimeout(timeoutId)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [error, fixedItems, loading, fixingItems, deletingItems, status])

  const parseBlockedReasons = (reasons) => {
    const documents = []
    const notes = []
    
    reasons.forEach(reason => {
      // Format: document_191_sanitize_level_too_low eller note_134_sanitize_level_too_low
      const docMatch = reason.match(/^document_(\d+)_sanitize_level_too_low$/)
      const noteMatch = reason.match(/^note_(\d+)_sanitize_level_too_low$/)
      
      if (docMatch) {
        documents.push({ id: parseInt(docMatch[1]), type: 'document' })
      } else if (noteMatch) {
        notes.push({ id: parseInt(noteMatch[1]), type: 'note' })
      }
    })
    
    return { documents, notes }
  }

  const handleFixItem = async (item) => {
    const itemKey = `${item.type}_${item.id}`
    if (fixingItems.has(itemKey) || fixedItems.has(itemKey)) return
    
    setFixingItems(prev => new Set(prev).add(itemKey))
    
    const username = 'admin'
    const password = 'password'
    const auth = btoa(`${username}:${password}`)
    
    try {
      const endpoint = item.type === 'document'
        ? apiUrl(`/projects/${projectId}/documents/${item.id}/sanitize?level=strict`)
        : apiUrl(`/projects/${projectId}/notes/${item.id}/sanitize?level=strict`)
      
      const response = await fetch(endpoint, {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      
      if (response.ok) {
        setFixedItems(prev => new Set(prev).add(itemKey))
        setFixErrors(prev => {
          const next = new Map(prev)
          next.delete(itemKey)
          return next
        })
        setFixingItems(prev => {
          const next = new Set(prev)
          next.delete(itemKey)
          return next
        })
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || `Kunde inte åtgärda ${item.type}`)
      }
    } catch (err) {
      console.error(`Failed to fix ${item.type} ${item.id}:`, err)
      setFixErrors(prev => new Map(prev).set(itemKey, err.message || 'Kunde inte uppdatera'))
      setFixingItems(prev => {
        const next = new Set(prev)
        next.delete(itemKey)
        return next
      })
    }
  }

  const handleEditDocument = async (docId, e) => {
    e.preventDefault()
    e.stopPropagation()
    
    setDocumentLoading(true)
    
    const username = 'admin'
    const password = 'password'
    const auth = btoa(`${username}:${password}`)
    
    try {
      const response = await fetch(apiUrl(`/documents/${docId}`), {
        headers: { 'Authorization': `Basic ${auth}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setEditingDocument(data)
        setEditDocumentText(data.masked_text)
        setShowEditDocumentModal(true)
      } else {
        throw new Error('Kunde inte hämta dokument')
      }
    } catch (err) {
      console.error(`Failed to fetch document ${docId}:`, err)
      alert(`Kunde inte hämta dokument: ${err.message}`)
    } finally {
      setDocumentLoading(false)
    }
  }

  const handleSaveDocument = async () => {
    if (!editingDocument) return
    
    setSavingDocument(true)
    
    const username = 'admin'
    const password = 'password'
    const auth = btoa(`${username}:${password}`)
    
    try {
      const response = await fetch(apiUrl(`/documents/${editingDocument.id}`), {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          masked_text: editDocumentText
        })
      })
      
      if (response.ok) {
        const updatedDoc = await response.json()
        setEditingDocument(updatedDoc)
        setShowEditDocumentModal(false)
        setEditingDocument(null)
        setEditDocumentText('')
        
        // Clear error and report to trigger re-compile
        setError(null)
        setReport(null)
        setFixedItems(new Set())
        setFixErrors(new Map())
        setAutoCompileAfterExclude(true)
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || 'Kunde inte uppdatera dokument')
      }
    } catch (err) {
      console.error(`Failed to update document:`, err)
      alert(`Kunde inte uppdatera dokument: ${err.message}`)
    } finally {
      setSavingDocument(false)
    }
  }

  const handleOpenDocument = async (docId, e) => {
    e.preventDefault()
    e.stopPropagation()
    
    setDocumentLoading(true)
    setShowDocumentModal(true)
    
    const username = 'admin'
    const password = 'password'
    const auth = btoa(`${username}:${password}`)
    
    try {
      const response = await fetch(apiUrl(`/documents/${docId}`), {
        headers: { 'Authorization': `Basic ${auth}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setSelectedDocument(data)
      } else {
        throw new Error('Kunde inte hämta dokument')
      }
    } catch (err) {
      console.error(`Failed to fetch document ${docId}:`, err)
      alert(`Kunde inte hämta dokument: ${err.message}`)
      setShowDocumentModal(false)
    } finally {
      setDocumentLoading(false)
    }
  }

  const handleExcludeDocument = async (docId, e) => {
    e.preventDefault()
    e.stopPropagation()
    
    const itemKey = `document_${docId}`
    if (deletingItems.has(itemKey)) return
    
    setDeletingItems(prev => new Set(prev).add(itemKey))
    
    const username = 'admin'
    const password = 'password'
    const auth = btoa(`${username}:${password}`)
    
    try {
      const response = await fetch(apiUrl(`/projects/${projectId}/documents/${docId}/exclude-from-fortknox?exclude=true`), {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      
      if (response.ok) {
        // Clear error and report, then auto-compile
        // Don't clear error immediately - let it clear after successful compile
        setReport(null)
        setFixedItems(new Set())
        setFixErrors(new Map())
        // Trigger auto-compile after deletingItems is cleared
        // Use a longer delay to ensure state is fully updated
        setTimeout(() => {
          setAutoCompileAfterExclude(true)
        }, 500)
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || 'Kunde inte exkludera dokument')
      }
    } catch (err) {
      console.error(`Failed to exclude document ${docId}:`, err)
      alert(`Kunde inte exkludera dokument: ${err.message}`)
    } finally {
      setDeletingItems(prev => {
        const next = new Set(prev)
        next.delete(itemKey)
        return next
      })
    }
  }

  const handleOpenNote = async (noteId, e) => {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    
    setNoteLoading(true)
    setShowNoteModal(true)
    
    const username = 'admin'
    const password = 'password'
    const auth = btoa(`${username}:${password}`)
    
    try {
      const response = await fetch(apiUrl(`/notes/${noteId}`), {
        headers: { 'Authorization': `Basic ${auth}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setSelectedNote(data)
      } else {
        throw new Error('Kunde inte hämta anteckning')
      }
    } catch (err) {
      console.error(`Failed to fetch note ${noteId}:`, err)
      alert(`Kunde inte hämta anteckning: ${err.message}`)
      setShowNoteModal(false)
    } finally {
      setNoteLoading(false)
    }
  }

  const handleEditNote = async (noteId) => {
    // If note is already loaded and matches, use it
    if (selectedNote && selectedNote.id === noteId) {
      setEditNoteTitle(selectedNote.title || '')
      setEditNoteBody(selectedNote.masked_body || '')
      setEditingNote(selectedNote)
      setShowEditNoteModal(true)
      return
    }
    
    // Otherwise fetch note first
    setNoteLoading(true)
    const username = 'admin'
    const password = 'password'
    const auth = btoa(`${username}:${password}`)
    
    try {
      const response = await fetch(apiUrl(`/notes/${noteId}`), {
        headers: { 'Authorization': `Basic ${auth}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setSelectedNote(data)
        setEditNoteTitle(data.title || '')
        setEditNoteBody(data.masked_body || '')
        setEditingNote(data)
        setShowEditNoteModal(true)
      } else {
        throw new Error('Kunde inte hämta anteckning')
      }
    } catch (err) {
      console.error(`Failed to fetch note ${noteId}:`, err)
      alert(`Kunde inte hämta anteckning: ${err.message}`)
    } finally {
      setNoteLoading(false)
    }
  }

  const handleSaveNote = async () => {
    if (!editingNote) return
    
    setSavingNote(true)
    
    const username = 'admin'
    const password = 'password'
    const auth = btoa(`${username}:${password}`)
    
    try {
      const response = await fetch(apiUrl(`/projects/${projectId}/notes/${editingNote.id}`), {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: editNoteTitle,
          body: editNoteBody
        })
      })
      
      if (response.ok) {
        const updatedNote = await response.json()
        setSelectedNote(updatedNote)
        setEditingNote(updatedNote)
        setShowEditNoteModal(false)
        setEditingNote(null)
        setEditNoteTitle('')
        setEditNoteBody('')
        
        // Clear error and report to trigger re-compile
        setReport(null)
        setFixedItems(new Set())
        setFixErrors(new Map())
        setAutoCompileAfterExclude(true)
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || 'Kunde inte uppdatera anteckning')
      }
    } catch (err) {
      console.error(`Failed to update note:`, err)
      alert(`Kunde inte uppdatera anteckning: ${err.message}`)
    } finally {
      setSavingNote(false)
    }
  }

  const handleExcludeNote = async (noteId, e) => {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    
    const itemKey = `note_${noteId}`
    if (deletingItems.has(itemKey)) {
      return
    }
    
    setDeletingItems(prev => new Set(prev).add(itemKey))
    
    const username = 'admin'
    const password = 'password'
    const auth = btoa(`${username}:${password}`)
    
    try {
      const response = await fetch(apiUrl(`/projects/${projectId}/notes/${noteId}/exclude-from-fortknox?exclude=true`), {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      
      if (response.ok) {
        // Clear error and report, then auto-compile
        // Don't clear error immediately - let it clear after successful compile
        setReport(null)
        setFixedItems(new Set())
        setFixErrors(new Map())
        // Trigger auto-compile after deletingItems is cleared
        // Use a longer delay to ensure state is fully updated
        setTimeout(() => {
          setAutoCompileAfterExclude(true)
        }, 500)
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || 'Kunde inte exkludera anteckning')
      }
    } catch (err) {
      console.error(`Failed to exclude note ${noteId}:`, err)
      alert(`Kunde inte exkludera anteckning: ${err.message}`)
    } finally {
      setDeletingItems(prev => {
        const next = new Set(prev)
        next.delete(itemKey)
        return next
      })
    }
  }

  const handleCompile = async () => {
    setLoading(true)
    setError(null)
    
    const username = 'admin'
    const password = 'password'
    const auth = btoa(`${username}:${password}`)
    
    const controller = new AbortController()
    // Lokal LLM kan ta tid. Backend default är 180s (FORTKNOX_REMOTE_TIMEOUT),
    // så frontend måste tolerera längre körningar än 30s.
    const timeoutId = setTimeout(() => controller.abort(), 180000)

    const requestBody = {
      project_id: parseInt(projectId),
      policy_id: policyId,
      template_id: templateId
    }

    try {
      // Försök async jobs först (demo-safe: backend svarar 409 om avstängt)
      let response = await fetch(apiUrl('/fortknox/compile/jobs'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${auth}`
        },
        body: JSON.stringify(requestBody)
      })

      if (response.status === 202) {
        const job = await response.json()
        clearTimeout(timeoutId)

        const finalJob = await pollJob(job.id, { auth, timeoutMs: 180000 })
        if (String(finalJob.status) !== 'succeeded') {
          setError({ error_code: finalJob.error_code || 'JOB_FAILED', reasons: [finalJob.error_detail || 'Job failed'], detail: null })
          setReport(null)
          setIsCacheHit(false)
          return
        }

        const reportId = finalJob?.result?.data?.id
        if (!reportId) {
          setError({ error_code: 'JOB_NO_REPORT_ID', reasons: ['Job saknar rapport-id'], detail: null })
          setReport(null)
          setIsCacheHit(false)
          return
        }

        const reportRes = await fetch(apiUrl(`/fortknox/reports/${reportId}`), {
          headers: { 'Authorization': `Basic ${auth}` }
        })
        if (!reportRes.ok) {
          setError({ error_code: 'JOB_REPORT_FETCH_FAILED', reasons: [`HTTP ${reportRes.status}`], detail: null })
          setReport(null)
          setIsCacheHit(false)
          return
        }

        const data = await reportRes.json()
        const cacheHit = lastReportId !== null && data.id === lastReportId
        setIsCacheHit(cacheHit)
        setReport(data)
        setError(null)
        setLastReportId(data.id)
        setFixedItems(new Set())
        setFixErrors(new Map())
        return
      }

      // Fallback till sync
      if (response.status === 409) {
        response = await fetch(apiUrl('/fortknox/compile'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Basic ${auth}`
          },
          body: JSON.stringify(requestBody),
          signal: controller.signal
        })
      }

      clearTimeout(timeoutId)

      if (response.ok) {
        const data = await response.json()
        const cacheHit = lastReportId !== null && data.id === lastReportId
        setIsCacheHit(cacheHit)
        setReport(data)
        setError(null)
        setLastReportId(data.id)
        setFixedItems(new Set()) // Reset fixed items on new compile
        setFixErrors(new Map()) // Reset fix errors
      } else {
        const errorData = await response.json().catch(async () => {
          // If JSON parsing fails, try to get text
          const text = await response.text().catch(() => 'Unknown error')
          return { detail: text }
        })
        
        const parsedError = parseKnoxError(errorData)
        setError(parsedError)
        setReport(null)
        setIsCacheHit(false)
      }
    } catch (err) {
      clearTimeout(timeoutId)
      if (err.name === 'AbortError') {
        setError({ error_code: 'TIMEOUT', reasons: ['Request timeout after 180s'], detail: null })
      } else {
        setError({ error_code: 'NETWORK_ERROR', reasons: [err.message || 'Network error'], detail: null })
      }
      setReport(null)
      setIsCacheHit(false)
    } finally {
      setLoading(false)
    }
  }

  const saveReportAsDocument = async () => {
    if (!projectId || !report?.id) return
    setSavingReportDoc(true)
    setSavedReportDoc(null)
    try {
      const response = await fetch(apiUrl(`/projects/${projectId}/documents/from-knox-report`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${auth}`
        },
        body: JSON.stringify({ report_id: report.id })
      })
      if (!response.ok) {
        const errorData = await response.json().catch(async () => {
          const text = await response.text().catch(() => 'Unknown error')
          return { detail: text }
        })
        const parsed = parseKnoxError(errorData)
        throw new Error(parsed?.detail || parsed?.error_code || 'Kunde inte spara rapport som dokument')
      }
      const doc = await response.json()
      setSavedReportDoc({ id: doc.id, filename: doc.filename })
    } catch (e) {
      console.error('Failed to save Knox report as document:', e)
      alert(e?.message || 'Kunde inte spara rapport som dokument')
    } finally {
      setSavingReportDoc(false)
    }
  }

  const renderMarkdown = (markdown) => {
    if (!markdown) return null
    
    const lines = markdown.split('\n')
    const elements = []
    let currentParagraph = []
    
    lines.forEach((line, index) => {
      const trimmed = line.trim()
      
      if (trimmed.startsWith('# ')) {
        if (currentParagraph.length > 0) {
          elements.push(<p key={`p-${index}`} className="fortknox-markdown-p">{currentParagraph.join(' ')}</p>)
          currentParagraph = []
        }
        elements.push(<h1 key={`h1-${index}`} className="fortknox-markdown-h1">{trimmed.substring(2)}</h1>)
      } else if (trimmed.startsWith('## ')) {
        if (currentParagraph.length > 0) {
          elements.push(<p key={`p-${index}`} className="fortknox-markdown-p">{currentParagraph.join(' ')}</p>)
          currentParagraph = []
        }
        elements.push(<h2 key={`h2-${index}`} className="fortknox-markdown-h2">{trimmed.substring(3)}</h2>)
      } else if (trimmed.startsWith('- ')) {
        if (currentParagraph.length > 0) {
          elements.push(<p key={`p-${index}`} className="fortknox-markdown-p">{currentParagraph.join(' ')}</p>)
          currentParagraph = []
        }
        elements.push(<li key={`li-${index}`} className="fortknox-markdown-li">{trimmed.substring(2)}</li>)
      } else if (trimmed === '') {
        if (currentParagraph.length > 0) {
          elements.push(<p key={`p-${index}`} className="fortknox-markdown-p">{currentParagraph.join(' ')}</p>)
          currentParagraph = []
        }
      } else {
        currentParagraph.push(trimmed)
      }
    })
    
    if (currentParagraph.length > 0) {
      elements.push(<p key="p-final" className="fortknox-markdown-p">{currentParagraph.join(' ')}</p>)
    }
    
    return <div className="fortknox-markdown-content">{elements}</div>
  }

  const getStatusIcon = () => {
    switch (status) {
      case 'PASS':
        return <CheckCircle size={16} />
      case 'WORKING':
        return <Loader size={16} className="fortknox-status-spinner" />
      case 'BLOCKED':
        return <XCircle size={16} />
      case 'OFFLINE':
        return <AlertCircle size={16} />
      case 'ERROR':
        return <AlertTriangle size={16} />
      default:
        return <Lock size={16} />
    }
  }

  const getStatusLabel = () => {
    switch (status) {
      case 'PASS': return policyId === 'internal' ? 'Intern sammanställning klar' : 'Extern sammanställning klar'
      case 'WORKING': return 'ARBETAR'
      case 'BLOCKED': return 'BLOCKERAD'
      case 'OFFLINE': return 'OFFLINE'
      case 'ERROR': return 'FEL'
      default: return 'REDO'
    }
  }

  const getStatusVariant = () => {
    switch (status) {
      case 'PASS': return 'normal'
      case 'WORKING': return 'normal'
      case 'BLOCKED': return 'sensitive'
      case 'OFFLINE': return 'sensitive'
      case 'ERROR': return 'sensitive'
      default: return 'normal'
    }
  }

  const blockedItems = error && status === 'BLOCKED' ? parseBlockedReasons(error.reasons || []) : { documents: [], notes: [] }
  const allItemsFixed = blockedItems.documents.length > 0 && blockedItems.notes.length > 0 && 
    blockedItems.documents.every(d => fixedItems.has(`document_${d.id}`)) &&
    blockedItems.notes.every(n => fixedItems.has(`note_${n.id}`))

  return (
    <div className="fortknox-panel sidebar-section">
      <div className="fortknox-header">
        <div className="fortknox-header-left">
          <Lock size={20} className="fortknox-lock-icon" />
          <div>
            <h3 className="fortknox-title">Fort Knox</h3>
            <p className="fortknox-subtitle">Isolerad sammanställning med strikt integritet</p>
          </div>
        </div>
        <Badge variant={getStatusVariant()} className={`fortknox-status-badge fortknox-status-${status.toLowerCase()}`}>
          {getStatusIcon()}
          <span>{getStatusLabel()}</span>
        </Badge>
      </div>

      <div className="fortknox-controls">
        <div className="fortknox-policy-selector">
          <button
            className={`fortknox-segmented-btn ${policyId === 'internal' ? 'active' : ''}`}
            onClick={() => {
              setPolicyId('internal')
              setReport(null)
              setError(null)
              setIsCacheHit(false)
              setFixedItems(new Set())
            }}
            disabled={loading}
          >
            Intern
          </button>
          <button
            className={`fortknox-segmented-btn ${policyId === 'external' ? 'active' : ''}`}
            onClick={() => {
              setPolicyId('external')
              setReport(null)
              setError(null)
              setIsCacheHit(false)
              setFixedItems(new Set())
            }}
            disabled={loading}
          >
            Extern
          </button>
        </div>

        <div className="fortknox-template-selector">
          <Select
            value={templateId}
            onChange={(e) => {
              setTemplateId(e.target.value)
              setReport(null)
              setError(null)
              setIsCacheHit(false)
              setFixedItems(new Set())
            }}
            disabled={loading}
            className="fortknox-template-select"
          >
            <option value="weekly">Weekly</option>
          </Select>
        </div>

        <Button
          variant="primary"
          onClick={handleCompile}
          disabled={loading}
          className="fortknox-compile-btn"
          title={report ? "Alla sammanställningar är deterministiska och idempotenta" : undefined}
        >
          {loading ? 'Kompilerar...' : 'Kompilera rapport'}
        </Button>

        {report && (
          <p className="fortknox-idempotency-hint">
            Idempotent: samma underlag ger alltid samma rapport
          </p>
        )}
      </div>

      {loading && (
        <div className="fortknox-loading">
          <div className="fortknox-skeleton shimmer"></div>
          <div className="fortknox-skeleton shimmer"></div>
          <div className="fortknox-skeleton shimmer" style={{ width: '60%' }}></div>
          <div className="fortknox-loading-hint">Detta kan ta 1–3 min (lokal modell).</div>
        </div>
      )}

      {/* BLOCKED State - Fix-it Flow */}
      {error && !loading && status === 'BLOCKED' && (
        <div className="fortknox-blocked-card">
          <h4 className="fortknox-blocked-title">Extern export stoppad</h4>
          <p className="fortknox-blocked-explanation">
            Materialet i projektet uppfyller ännu inte kraven för extern användning.
            Inget innehåll har exponerats eller analyserats externt.
          </p>
          
          {(blockedItems.documents.length > 0 || blockedItems.notes.length > 0) && (
            <>
              <h5 className="fortknox-blocked-section-title">Vad blockerar?</h5>
              <div className="fortknox-blocked-items">
                {blockedItems.documents.length > 0 && (
                  <div className="fortknox-blocked-group">
                    <div className="fortknox-blocked-group-header">
                      <FileText size={16} />
                      <span>Dokument som inte är Extern-redo</span>
                    </div>
                    <ul className="fortknox-blocked-list">
                      {blockedItems.documents.map(doc => {
                        const itemKey = `document_${doc.id}`
                        const isFixed = fixedItems.has(itemKey)
                        const isFixing = fixingItems.has(itemKey)
                        const isDeleting = deletingItems.has(itemKey)
                        const fixError = fixErrors.get(itemKey)
                        const isFileNotFound = fixError && fixError.includes('Original file not found')
                        return (
                            <li key={doc.id} className="fortknox-blocked-item">
                            <div className="fortknox-blocked-item-content">
                              <div className="fortknox-blocked-item-actions">
                                <button
                                  onClick={(e) => handleOpenDocument(doc.id, e)}
                                  className="fortknox-blocked-item-link"
                                  disabled={isDeleting || documentLoading}
                                  title="Visa dokument"
                                  type="button"
                                >
                                  <span className="fortknox-blocked-item-id">Dokument {doc.id}</span>
                                </button>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={(e) => handleEditDocument(doc.id, e)}
                                  disabled={documentLoading || savingDocument}
                                  className="fortknox-edit-doc-btn"
                                  title="Redigera dokument"
                                >
                                  <Edit size={14} />
                                </Button>
                              </div>
                              {isFixed ? (
                                <Badge variant="normal" className="fortknox-fixed-badge">Extern-redo</Badge>
                              ) : (
                                <>
                                  <Badge variant="sensitive" className="fortknox-not-ready-badge">Ej Extern-redo</Badge>
                                  {fixError ? (
                                    <div className="fortknox-error-actions">
                                      <span className="fortknox-fix-error">{fixError}</span>
                                      {isFileNotFound && (
                                        <Button
                                          variant="secondary"
                                          size="sm"
                                          onClick={(e) => handleExcludeDocument(doc.id, e)}
                                          disabled={isDeleting}
                                          className="fortknox-exclude-btn"
                                        >
                                          {isDeleting ? 'Exkluderar...' : 'Exkludera från sammanställning'}
                                        </Button>
                                      )}
                                    </div>
                                  ) : (
                                    <Button
                                      variant="secondary"
                                      size="sm"
                                      onClick={() => handleFixItem(doc)}
                                      disabled={isFixing}
                                      className="fortknox-fix-btn"
                                    >
                                      {isFixing ? 'Uppdaterar...' : 'Gör Extern-redo'}
                                    </Button>
                                  )}
                                </>
                              )}
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )}
                
                {blockedItems.notes.length > 0 && (
                  <div className="fortknox-blocked-group">
                    <div className="fortknox-blocked-group-header">
                      <StickyNote size={16} />
                      <span>Anteckningar som inte är Extern-redo</span>
                    </div>
                    <ul className="fortknox-blocked-list">
                      {blockedItems.notes.map(note => {
                        const itemKey = `note_${note.id}`
                        const isFixed = fixedItems.has(itemKey)
                        const isFixing = fixingItems.has(itemKey)
                        const fixError = fixErrors.get(itemKey)
                        return (
                          <li key={note.id} className="fortknox-blocked-item">
                            <div className="fortknox-blocked-item-content">
                              <div className="fortknox-blocked-item-actions">
                                <button
                                  onClick={(e) => handleOpenNote(note.id, e)}
                                  className="fortknox-blocked-item-link fortknox-note-link"
                                  type="button"
                                  disabled={noteLoading}
                                  title="Visa anteckning"
                                >
                                  <span className="fortknox-blocked-item-id">Anteckning {note.id}</span>
                                </button>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => handleEditNote(note.id)}
                                  disabled={noteLoading || savingNote}
                                  className="fortknox-edit-note-btn"
                                  title="Redigera anteckning"
                                >
                                  <Edit size={14} />
                                </Button>
                              </div>
                              {isFixed ? (
                                <Badge variant="normal" className="fortknox-fixed-badge">Extern-redo</Badge>
                              ) : (
                                <>
                                  <Badge variant="sensitive" className="fortknox-not-ready-badge">Ej Extern-redo</Badge>
                                  {fixError ? (
                                    <div className="fortknox-error-actions">
                                      <span className="fortknox-fix-error">{fixError}</span>
                                      <Button
                                        variant="secondary"
                                        size="sm"
                                        onClick={(e) => {
                                          if (e) {
                                            e.preventDefault()
                                            e.stopPropagation()
                                            e.nativeEvent?.stopImmediatePropagation()
                                          }
                                          handleExcludeNote(note.id, e)
                                          return false
                                        }}
                                        disabled={deletingItems.has(`note_${note.id}`)}
                                        className="fortknox-exclude-btn"
                                        type="button"
                                      >
                                        {deletingItems.has(`note_${note.id}`) ? 'Exkluderar...' : 'Exkludera från sammanställning'}
                                      </Button>
                                    </div>
                                  ) : (
                                    <div className="fortknox-note-actions">
                                      <span className="fortknox-note-limitation">
                                        Anteckningar kan inte uppgraderas automatiskt. Klicka på anteckningen för att redigera.
                                      </span>
                                      <Button
                                        variant="secondary"
                                        size="sm"
                                        onClick={(e) => {
                                          if (e) {
                                            e.preventDefault()
                                            e.stopPropagation()
                                            e.nativeEvent?.stopImmediatePropagation()
                                          }
                                          handleExcludeNote(note.id, e)
                                          return false
                                        }}
                                        disabled={deletingItems.has(`note_${note.id}`)}
                                        className="fortknox-exclude-btn"
                                        type="button"
                                      >
                                        {deletingItems.has(`note_${note.id}`) ? 'Exkluderar...' : 'Exkludera'}
                                      </Button>
                                    </div>
                                  )}
                                </>
                              )}
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )}
              </div>
              
              <p className="fortknox-blocked-help">
                Extern policy kräver strikt sanering. Detta säkerställer att inga citat, personuppgifter eller identifierande formuleringar kan återskapas.
              </p>
              
              {allItemsFixed && (
                <div className="fortknox-all-fixed">
                  <p className="fortknox-all-fixed-text">
                    Materialet uppfyller nu kraven för extern policy. Klicka "Kompilera rapport" för att fortsätta.
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* OFFLINE State */}
      {error && !loading && status === 'OFFLINE' && (
        <div className="fortknox-error-card fortknox-offline-card">
          <h4 className="fortknox-error-title">Fort Knox är offline</h4>
          <p className="fortknox-error-text">
            Den lokala sammanställningsmiljön är inte tillgänglig just nu.
            Inget innehåll har skickats eller köats.
          </p>
        </div>
      )}

      {/* ERROR State */}
      {error && !loading && status === 'ERROR' && (
        <div className="fortknox-error-card fortknox-error-state-card">
          {error.error_code === 'EMPTY_INPUT_SET' ? (
            <>
              <h4 className="fortknox-error-title">Tomt underlag</h4>
              <p className="fortknox-error-text">
                Du har exkluderat allt underlag från sammanställningen. Välj minst ett dokument, anteckning eller källa för att kompilera en rapport.
              </p>
            </>
          ) : error.error_code === 'VALIDATION_ERROR' ? (
            <>
              <h4 className="fortknox-error-title">Valideringsfel</h4>
              <p className="fortknox-error-text">
                Begäran kunde inte valideras. Kontrollera att alla fält är korrekt ifyllda.
              </p>
              {error.reasons && error.reasons.length > 0 && (
                <ul className="fortknox-error-reasons">
                  {error.reasons.slice(0, 5).map((reason, idx) => (
                    <li key={idx}>{reason}</li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <>
              <h4 className="fortknox-error-title">Tekniskt fel</h4>
              <p className="fortknox-error-text">
                Sammanställningen kunde inte slutföras. Ingen data har läckt eller bearbetats delvis.
              </p>
              {error.error_code && (
                <div className="fortknox-error-code">Error: {error.error_code}</div>
              )}
              {error.reasons && error.reasons.length > 0 && (
                <ul className="fortknox-error-reasons">
                  {error.reasons.slice(0, 5).map((reason, idx) => (
                    <li key={idx}>{reason}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      )}

      {/* Report Display */}
      {report && !loading && (
        <div className="fortknox-report-container">
          <div className="fortknox-report-header">
            <h4 className="fortknox-report-title">
              <CheckCircle size={18} />
              <span>Rapport genererad</span>
            </h4>
            <div className="fortknox-report-header-actions">
              <Button
                variant="secondary"
                onClick={saveReportAsDocument}
                disabled={savingReportDoc}
              >
                {savingReportDoc ? 'Sparar...' : 'Spara som dokument'}
              </Button>
              {savedReportDoc && (
                <span className="fortknox-report-saved">
                  Sparat: {savedReportDoc.filename}
                </span>
              )}
            </div>
          </div>
          {policyId === 'internal' && (
            <div className="fortknox-report-info">
              Denna sammanställning är framtagen för internt bruk. Allt material har normaliserats, sanerats och verifierats innan analys.
            </div>
          )}
          {policyId === 'external' && (
            <div className="fortknox-report-info fortknox-report-info-external">
              Denna sammanställning är framtagen för extern användning. Allt material har genomgått strikt sanering och verifierats innan analys.
            </div>
          )}
          <div className="fortknox-report-paper">
            {renderMarkdown(report.rendered_markdown)}
          </div>
          <div className="fortknox-audit-footer">
            {isCacheHit && (
              <Badge variant="normal" className="fortknox-cache-badge">Cache-hit</Badge>
            )}
            {report.input_fingerprint && (
              <span className="fortknox-audit-item">Ingångsfingerprint: {report.input_fingerprint.substring(0, 16)}...</span>
            )}
            {report.policy_version && (
              <span className="fortknox-audit-item">Policy: {report.policy_version}</span>
            )}
            {report.ruleset_hash && (
              <span className="fortknox-audit-item">Ruleset: {report.ruleset_hash.substring(0, 8)}</span>
            )}
            {report.id && (
              <span className="fortknox-audit-item">Rapport-ID: {report.id}</span>
            )}
          </div>
        </div>
      )}

      {/* Document Modal */}
      <Modal
        isOpen={showDocumentModal}
        onClose={() => {
          setShowDocumentModal(false)
          setSelectedDocument(null)
        }}
        title={selectedDocument ? selectedDocument.filename : 'Laddar dokument...'}
      >
        {documentLoading ? (
          <div className="fortknox-document-loading">
            <Loader size={24} className="spinning" />
            <p>Laddar dokument...</p>
          </div>
        ) : selectedDocument ? (
          <div className="fortknox-document-modal">
            <div className="fortknox-document-meta">
              <div className="fortknox-document-meta-row">
                <span className="fortknox-document-meta-label">Typ:</span>
                <Badge variant={selectedDocument.classification === 'sensitive' || selectedDocument.classification === 'source-sensitive' ? 'sensitive' : 'normal'}>
                  {selectedDocument.classification === 'source-sensitive' ? 'Källkritisk' : selectedDocument.classification === 'sensitive' ? 'Känslig' : 'Offentlig'}
                </Badge>
              </div>
              <div className="fortknox-document-meta-row">
                <span className="fortknox-document-meta-label">Saneringsnivå:</span>
                <Badge variant={selectedDocument.sanitize_level === 'paranoid' ? 'sensitive' : 'normal'}>
                  {selectedDocument.sanitize_level === 'normal' ? 'Normal' : selectedDocument.sanitize_level === 'strict' ? 'Strikt' : 'Paranoid'}
                </Badge>
              </div>
              <div className="fortknox-document-meta-row">
                <span className="fortknox-document-meta-label">Skapad:</span>
                <span>{new Date(selectedDocument.created_at).toLocaleDateString('sv-SE')}</span>
              </div>
              <div className="fortknox-document-meta-masked">
                <Info size={14} />
                <span>Maskad vy – Originalmaterial bevaras i säkert lager</span>
              </div>
            </div>
            <div className="fortknox-document-text">
              {selectedDocument.masked_text.split('\n').map((line, index) => (
                <p key={index} className="fortknox-document-line">
                  {line || '\u00A0'}
                </p>
              ))}
            </div>
          </div>
        ) : null}
      </Modal>

      {/* Edit Document Modal */}
      <Modal
        isOpen={showEditDocumentModal}
        onClose={() => {
          setShowEditDocumentModal(false)
          setEditingDocument(null)
          setEditDocumentText('')
        }}
        title={editingDocument ? `Redigera: ${editingDocument.filename}` : 'Redigera dokument'}
      >
        {editingDocument ? (
          <div className="fortknox-edit-document-modal">
            <div className="fortknox-edit-document-meta">
              <div className="fortknox-edit-document-meta-row">
                <span className="fortknox-edit-document-meta-label">Typ:</span>
                <Badge variant={editingDocument.classification === 'sensitive' || editingDocument.classification === 'source-sensitive' ? 'sensitive' : 'normal'}>
                  {editingDocument.classification === 'source-sensitive' ? 'Källkritisk' : editingDocument.classification === 'sensitive' ? 'Känslig' : 'Offentlig'}
                </Badge>
              </div>
              <div className="fortknox-edit-document-meta-row">
                <span className="fortknox-edit-document-meta-label">Saneringsnivå:</span>
                <Badge variant={editingDocument.sanitize_level === 'paranoid' ? 'sensitive' : 'normal'}>
                  {editingDocument.sanitize_level === 'normal' ? 'Normal' : editingDocument.sanitize_level === 'strict' ? 'Strikt' : 'Paranoid'}
                </Badge>
              </div>
              <div className="fortknox-edit-document-meta-masked">
                <Info size={14} />
                <span>Texten kommer att normaliseras och saneras automatiskt efter sparning</span>
              </div>
            </div>
            <div className="fortknox-edit-document-textarea-container">
              <textarea
                className="fortknox-edit-document-textarea"
                value={editDocumentText}
                onChange={(e) => setEditDocumentText(e.target.value)}
                placeholder="Skriv eller redigera dokumenttext här..."
                rows={15}
              />
            </div>
            <div className="fortknox-edit-document-actions">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowEditDocumentModal(false)
                  setEditingDocument(null)
                  setEditDocumentText('')
                }}
                disabled={savingDocument}
              >
                Avbryt
              </Button>
              <Button
                variant="primary"
                onClick={handleSaveDocument}
                disabled={savingDocument || !editDocumentText.trim()}
              >
                {savingDocument ? 'Sparar...' : 'Spara'}
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      {/* Note Modal */}
      <Modal
        isOpen={showNoteModal}
        onClose={() => {
          setShowNoteModal(false)
          setSelectedNote(null)
        }}
        title={selectedNote ? (selectedNote.title || `Anteckning ${selectedNote.id}`) : 'Laddar anteckning...'}
      >
        {noteLoading ? (
          <div className="fortknox-document-loading">
            <Loader size={24} className="spinning" />
            <p>Laddar anteckning...</p>
          </div>
        ) : selectedNote ? (
          <div className="fortknox-document-modal">
            <div className="fortknox-document-meta">
              <div className="fortknox-document-meta-row">
                <span className="fortknox-document-meta-label">Saneringsnivå:</span>
                <Badge variant={selectedNote.sanitize_level === 'paranoid' ? 'sensitive' : 'normal'}>
                  {selectedNote.sanitize_level === 'normal' ? 'Normal' : selectedNote.sanitize_level === 'strict' ? 'Strikt' : 'Paranoid'}
                </Badge>
              </div>
              <div className="fortknox-document-meta-row">
                <span className="fortknox-document-meta-label">Skapad:</span>
                <span>{new Date(selectedNote.created_at).toLocaleDateString('sv-SE')}</span>
              </div>
              <div className="fortknox-document-meta-masked">
                <Info size={14} />
                <span>Maskad vy – Originalmaterial bevaras i säkert lager</span>
              </div>
            </div>
            <div className="fortknox-document-text">
              {selectedNote.masked_body ? selectedNote.masked_body.split('\n').map((line, index) => (
                <p key={index} className="fortknox-document-line">
                  {line || '\u00A0'}
                </p>
              )) : (
                <p className="fortknox-document-line">Inget innehåll</p>
              )}
            </div>
            <div className="fortknox-document-actions" style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
              <Button
                variant="secondary"
                onClick={() => handleEditNote(selectedNote.id)}
                disabled={savingNote}
              >
                <Edit size={14} style={{ marginRight: '0.25rem' }} />
                Redigera
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      {/* Edit Note Modal */}
      <Modal
        isOpen={showEditNoteModal}
        onClose={() => {
          setShowEditNoteModal(false)
          setEditingNote(null)
          setEditNoteTitle('')
          setEditNoteBody('')
        }}
        title={editingNote ? `Redigera: ${editingNote.title || `Anteckning ${editingNote.id}`}` : 'Redigera anteckning'}
      >
        {editingNote ? (
          <div className="fortknox-edit-document-modal">
            <div className="fortknox-edit-document-meta">
              <div className="fortknox-edit-document-meta-row">
                <span className="fortknox-edit-document-meta-label">Saneringsnivå:</span>
                <Badge variant={editingNote.sanitize_level === 'paranoid' ? 'sensitive' : 'normal'}>
                  {editingNote.sanitize_level === 'normal' ? 'Normal' : editingNote.sanitize_level === 'strict' ? 'Strikt' : 'Paranoid'}
                </Badge>
              </div>
              <div className="fortknox-edit-document-meta-masked">
                <Info size={14} />
                <span>Texten kommer att normaliseras och saneras automatiskt efter sparning</span>
              </div>
            </div>
            <div className="fortknox-edit-document-textarea-container" style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 500 }}>Titel:</label>
              <input
                type="text"
                className="fortknox-edit-document-textarea"
                value={editNoteTitle}
                onChange={(e) => setEditNoteTitle(e.target.value)}
                placeholder="Anteckningens titel..."
                style={{ padding: '0.5rem', fontSize: '1rem', width: '100%', marginBottom: '1rem' }}
              />
            </div>
            <div className="fortknox-edit-document-textarea-container">
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 500 }}>Innehåll:</label>
              <textarea
                className="fortknox-edit-document-textarea"
                value={editNoteBody}
                onChange={(e) => setEditNoteBody(e.target.value)}
                placeholder="Skriv eller redigera anteckningstext här..."
                rows={15}
              />
            </div>
            <div className="fortknox-edit-document-actions">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowEditNoteModal(false)
                  setEditingNote(null)
                  setEditNoteTitle('')
                  setEditNoteBody('')
                }}
                disabled={savingNote}
              >
                Avbryt
              </Button>
              <Button
                variant="primary"
                onClick={handleSaveNote}
                disabled={savingNote || !editNoteBody.trim()}
              >
                {savingNote ? 'Sparar...' : 'Spara'}
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}

export default FortKnoxPanel
