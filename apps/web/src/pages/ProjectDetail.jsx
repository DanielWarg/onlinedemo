import { useState, useEffect, useRef } from 'react'
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Modal } from '../ui/Modal'
import CreateProject from './CreateProject'
import { getDueUrgency } from '../lib/urgency'
import { apiUrl } from '../lib/api'
import { FileText, StickyNote, Mic, Upload, File, Info, Edit, Trash2, Lock } from 'lucide-react'
import JournalistNotes from './JournalistNotes'
import FortKnoxStation from '../components/FortKnoxStation'
import { pollJob } from '../lib/jobs'
import './ProjectDetail.css'

function ProjectDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [project, setProject] = useState(null)
  const [events, setEvents] = useState([])
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [ingestMode, setIngestMode] = useState('document') // document, note, audio
  const [showEditModal, setShowEditModal] = useState(false)
  const [sources, setSources] = useState([])
  const [projectNotes, setProjectNotes] = useState([])
  const [showAddSourceModal, setShowAddSourceModal] = useState(false)
  const [showEditSourceModal, setShowEditSourceModal] = useState(false)
  const [showEditNoteModal, setShowEditNoteModal] = useState(false)
  const [editingSource, setEditingSource] = useState(null)
  const [editingNote, setEditingNote] = useState(null)
  const [addingSource, setAddingSource] = useState(false)
  const [updatingSource, setUpdatingSource] = useState(false)
  const [updatingNote, setUpdatingNote] = useState(false)
  const [newSource, setNewSource] = useState({ title: '', type: 'link', url: '', comment: '' })
  const [editNoteBody, setEditNoteBody] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState({ show: false, type: null, id: null, name: '' })
  const [deleting, setDeleting] = useState(false)
  const [updatingStatus, setUpdatingStatus] = useState(false)
  const [showExportModal, setShowExportModal] = useState(false)
  const [exportSettings, setExportSettings] = useState({
    includeMetadata: true,
    includeTranscripts: false,
    includeNotes: false
  })
  const [exporting, setExporting] = useState(false)
  const [showFortKnoxStation, setShowFortKnoxStation] = useState(false)
  const fileInputRef = useRef(null)
  
  // Recording states
  const [recordingUploading, setRecordingUploading] = useState(false)
  const [recordingProcessing, setRecordingProcessing] = useState(false)
  const [recordingError, setRecordingError] = useState(null)
  const [recordingSuccess, setRecordingSuccess] = useState(null)
  const [showTranscriptModal, setShowTranscriptModal] = useState(false)
  const [transcriptDocId, setTranscriptDocId] = useState(null)
  const [transcriptPreview, setTranscriptPreview] = useState('')
  const [transcriptPreviewLoading, setTranscriptPreviewLoading] = useState(false)
  const [transcriptPreviewError, setTranscriptPreviewError] = useState(null)
  const audioInputRef = useRef(null)
  
  // MediaRecorder states
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0) // seconds
  const [recordingMode, setRecordingMode] = useState('record') // 'upload' | 'record' - default 'record' to show recording button
  const [micPermissionError, setMicPermissionError] = useState(null)
  
  // Refs to avoid stale state in callbacks
  const recorderRef = useRef(null)
  const timerRef = useRef(null)
  const streamRef = useRef(null)
  const audioChunksRef = useRef([])
  
  // Drag and drop state for audio
  const [isDraggingAudio, setIsDraggingAudio] = useState(false)

  const fetchProject = async () => {
    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)
      
      const [projectRes, eventsRes, documentsRes, sourcesRes, notesRes] = await Promise.all([
        fetch(apiUrl(`/projects/${id}`), {
          headers: { 'Authorization': `Basic ${auth}` }
        }),
        fetch(apiUrl(`/projects/${id}/events`), {
          headers: { 'Authorization': `Basic ${auth}` }
        }),
        fetch(apiUrl(`/projects/${id}/documents`), {
          headers: { 'Authorization': `Basic ${auth}` }
        }),
        fetch(apiUrl(`/projects/${id}/sources`), {
          headers: { 'Authorization': `Basic ${auth}` }
        }),
        fetch(apiUrl(`/projects/${id}/notes`), {
          headers: { 'Authorization': `Basic ${auth}` }
        })
      ])
      
      if (!projectRes.ok) throw new Error('Kunde inte hämta projekt')
      if (!eventsRes.ok) throw new Error('Kunde inte hämta händelser')
      
      const projectData = await projectRes.json()
      const eventsData = await eventsRes.json()
      const documentsData = documentsRes.ok ? await documentsRes.json() : []
      const sourcesData = sourcesRes.ok ? await sourcesRes.json() : []
      const notesData = notesRes.ok ? await notesRes.json() : []
      
      setProject(projectData)
      setEvents(eventsData)
      setDocuments(documentsData)
      setSources(sourcesData)
      setProjectNotes(notesData)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProject()
  }, [id])

  // Open note modal if navigated from Fort Knox
  useEffect(() => {
    if (location.state?.openNoteId && projectNotes.length > 0) {
      const note = projectNotes.find(n => n.id === location.state.openNoteId)
      if (note) {
        handleEditNote(note)
        // Clear state to prevent reopening on re-render
        navigate(location.pathname, { replace: true, state: {} })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectNotes, location.state?.openNoteId])

  const handleDropzoneClick = () => {
    const input = ingestMode === 'audio' ? audioInputRef.current : fileInputRef.current
    if (!input) return
    try {
      input.showPicker?.()
    } catch {
      // ignore
    }
    input.click()
  }

  const handleAudioSelect = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file size (25MB)
    if (file.size > 25 * 1024 * 1024) {
      setRecordingError('Filen är för stor. Maximal storlek är 25MB')
      return
    }

    setRecordingUploading(true)
    setRecordingProcessing(false)
    setRecordingError(null)
    setRecordingSuccess(null)

    try {
      // Validate file exists and has content
      if (!file || file.size === 0) {
        throw new Error('Filen är tom eller ogiltig')
      }

      const formData = new FormData()
      formData.append('file', file)

      // Add auth header (same as other fetch calls)
      const username = 'admin'
      const password = 'password'
      const auth = btoa(username + ':' + password)

      // Försök async jobs först (demo-safe: backend svarar 409 om avstängt)
      // NOTE: Do NOT set Content-Type header - browser will set it automatically with boundary for FormData
      let response = await fetch(apiUrl(`/projects/${id}/recordings/jobs`), {
        method: 'POST',
        headers: {
          'Authorization': 'Basic ' + auth
        },
        body: formData
      })

      // Fallback till sync
      if (response.status === 409) {
        response = await fetch(apiUrl(`/projects/${id}/recordings`), {
          method: 'POST',
          headers: {
            'Authorization': 'Basic ' + auth
          },
          body: formData
        })
      } else if (response.status === 202) {
        const job = await response.json()
        // Upload finished, now processing
        setRecordingUploading(false)
        setRecordingProcessing(true)

        const finalJob = await pollJob(job.id, { auth, timeoutMs: 180000 })
        if (String(finalJob.status) !== 'succeeded') {
          throw new Error(finalJob.error_detail || finalJob.error_code || 'Kunde inte processa röstmemo')
        }
        const docId = finalJob?.result?.data?.id
        if (!docId) throw new Error('Job saknar dokument-id')

        setRecordingProcessing(false)
        setRecordingSuccess({ documentId: docId })
        await fetchProject()
        return
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Kunde inte ladda upp ljudfil')
      }

      const documentData = await response.json()

      // Simulate processing delay (800-1200ms)
      setRecordingUploading(false)
      setRecordingProcessing(true)
      
      const delay = 800 + Math.random() * 400 // 800-1200ms
      await new Promise(resolve => setTimeout(resolve, delay))
      
      setRecordingProcessing(false)
      setRecordingSuccess({ documentId: documentData.id })

      // Refresh documents list
      await fetchProject()
    } catch (err) {
      setRecordingUploading(false)
      setRecordingProcessing(false)
      setRecordingError(err.message)
    } finally {
      // Reset file input
      if (audioInputRef.current) {
        audioInputRef.current.value = ''
      }
    }
  }

  // Drag and drop handlers for audio
  const handleAudioDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (!recordingUploading && !recordingProcessing) {
      setIsDraggingAudio(true)
    }
  }

  const handleAudioDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDraggingAudio(false)
  }

  const handleAudioDrop = async (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDraggingAudio(false)
    
    if (recordingUploading || recordingProcessing) {
      return
    }
    
    const files = e.dataTransfer.files
    if (files.length === 0) return
    
    const file = files[0]
    
    // Validate file type
    if (!file.type.startsWith('audio/')) {
      setRecordingError('Endast ljudfiler är tillåtna')
      return
    }
    
    // Create a synthetic event for handleAudioSelect
    const syntheticEvent = {
      target: { files: [file] }
    }
    
    await handleAudioSelect(syntheticEvent)
  }

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  // Simplified recording functions - avoid constructor issues
  const startRecording = async () => {
    try {
      setMicPermissionError(null)
      
      // Check browser support
      if (typeof window === 'undefined') return
      if (!window.MediaRecorder) {
        setMicPermissionError('MediaRecorder stöds inte i denna webbläsare')
        return
      }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setMicPermissionError('Mikrofon stöds inte i denna webbläsare')
        return
      }
      
      // Get microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      
      // Find supported MIME type - prefer ogg for better Whisper compatibility
      const mimeTypes = ['audio/ogg', 'audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
      let mimeType = ''
      for (const type of mimeTypes) {
        if (window.MediaRecorder.isTypeSupported(type)) {
          mimeType = type
          break
        }
      }
      console.log('Using MIME type:', mimeType)
      
      if (!mimeType) {
        stream.getTracks().forEach(t => t.stop())
        setMicPermissionError('Inget ljudformat stöds. Använd fil-uppladdning.')
        return
      }
      
      // Create recorder
      const recorder = new window.MediaRecorder(stream, { mimeType })
      recorderRef.current = recorder
      audioChunksRef.current = []
      
      recorder.ondataavailable = function(e) {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data)
        }
      }
      
      recorder.onstop = function() {
        // Clear timer
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        
        // Stop tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(t => t.stop())
          streamRef.current = null
        }
        
        // Create blob and upload - use all collected chunks
        if (audioChunksRef.current.length > 0) {
          const audioBlob = new window.Blob(audioChunksRef.current, { type: mimeType })
          console.log('Recording blob size:', audioBlob.size, 'chunks:', audioChunksRef.current.length)
          if (audioBlob.size > 0) {
            uploadRecordingBlob(audioBlob)
          } else {
            setRecordingError('Inspelningen är tom. Försök igen.')
          }
        } else {
          setRecordingError('Ingen ljuddata inspelad. Försök igen.')
        }
      }
      
      // Start with timeslice to get data every 250ms (ensures data is collected)
      recorder.start(250)
      setIsRecording(true)
      setRecordingTime(0)
      
      // Timer - auto stop at 30s
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => {
          if (prev >= 29) {
            stopRecording()
            return 30
          }
          return prev + 1
        })
      }, 1000)
      
    } catch (err) {
      // Cleanup
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop())
        streamRef.current = null
      }
      setMicPermissionError('Mikrofonåtkomst nekad: ' + (err.message || 'Okänt fel'))
    }
  }

  const stopRecording = () => {
    if (recorderRef.current && isRecording) {
      recorderRef.current.stop()
      setIsRecording(false)
    }
  }

  const uploadRecordingBlob = async (audioBlob) => {
    setRecordingUploading(true)
    setRecordingProcessing(false)
    setRecordingError(null)
    setRecordingSuccess(null)
    
    try {
      const ext = audioBlob.type.includes('webm') ? 'webm' : audioBlob.type.includes('ogg') ? 'ogg' : 'mp4'
      const filename = 'recording_' + Date.now() + '.' + ext
      
      const formData = new window.FormData()
      formData.append('file', audioBlob, filename)
      
      // Add auth header (same as other fetch calls)
      const username = 'admin'
      const password = 'password'
      const auth = btoa(username + ':' + password)
      
      // Försök async jobs först (demo-safe: backend svarar 409 om avstängt)
      let response = await fetch(apiUrl(`/projects/${id}/recordings/jobs`), {
        method: 'POST',
        headers: {
          'Authorization': 'Basic ' + auth
        },
        body: formData
      })

      // Fallback till sync
      if (response.status === 409) {
        response = await fetch(apiUrl(`/projects/${id}/recordings`), {
          method: 'POST',
          headers: {
            'Authorization': 'Basic ' + auth
          },
          body: formData
        })
      } else if (response.status === 202) {
        const job = await response.json()
        setRecordingUploading(false)
        setRecordingProcessing(true)

        const finalJob = await pollJob(job.id, { auth, timeoutMs: 180000 })
        if (String(finalJob.status) !== 'succeeded') {
          throw new Error(finalJob.error_detail || finalJob.error_code || 'Kunde inte processa inspelning')
        }
        const docId = finalJob?.result?.data?.id
        if (!docId) throw new Error('Job saknar dokument-id')

        await new Promise(r => setTimeout(r, 400))
        setRecordingProcessing(false)
        setRecordingSuccess({ documentId: docId })
        await fetchProject()
        return
      }
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Kunde inte ladda upp inspelning')
      }
      
      const documentData = await response.json()
      
      setRecordingUploading(false)
      setRecordingProcessing(true)
      
      // Brief delay for UX
      await new Promise(r => setTimeout(r, 800))
      
      setRecordingProcessing(false)
      setRecordingSuccess({ documentId: documentData.id })
      await fetchProject()
    } catch (err) {
      setRecordingUploading(false)
      setRecordingProcessing(false)
      setRecordingError(err.message || 'Uppladdning misslyckades')
    }
  }

  const openTranscriptPreview = async (documentId) => {
    setTranscriptDocId(documentId)
    setTranscriptPreview('')
    setTranscriptPreviewError(null)
    setShowTranscriptModal(true)
    setTranscriptPreviewLoading(true)

    try {
      const auth = btoa('admin:password')
      const res = await fetch(apiUrl(`/documents/${documentId}`), {
        headers: { 'Authorization': `Basic ${auth}` }
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const doc = await res.json()
      const text = String(doc.masked_text || '')
      const snippet = text.length > 1200 ? `${text.slice(0, 1200)}…` : text
      setTranscriptPreview(snippet)
    } catch (err) {
      setTranscriptPreviewError('Kunde inte hämta förhandsvisning. Öppna dokumentet för att se transkriptionen.')
    } finally {
      setTranscriptPreviewLoading(false)
    }
  }

  useEffect(() => {
    if (recordingSuccess?.documentId) {
      openTranscriptPreview(recordingSuccess.documentId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordingSuccess?.documentId])

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (ext !== 'pdf' && ext !== 'txt') {
      setUploadError('Endast PDF och TXT-filer är tillåtna')
      return
    }

    // Validate file size (25MB)
    if (file.size > 25 * 1024 * 1024) {
      setUploadError('Filen är för stor. Maximal storlek är 25MB')
      return
    }

    setUploading(true)
    setUploadError(null)

    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)

      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(apiUrl(`/projects/${id}/documents`), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`
        },
        body: formData
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Upload misslyckades')
      }

      // Refresh documents list
      await fetchProject()
      
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (err) {
      setUploadError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const getClassificationLabel = (classification) => {
    if (classification === 'source-sensitive') {
      return 'Källkritisk'
    }
    if (classification === 'sensitive') {
      return 'Känslig'
    }
    return 'Offentlig'
  }

  const getClassificationVariant = (classification) => {
    if (classification === 'source-sensitive') {
      return 'source-sensitive'
    }
    if (classification === 'sensitive') {
      return 'sensitive'
    }
    return 'normal'
  }

  const getDueDateStatus = (dueDate) => {
    if (!dueDate) return null
    const due = new Date(dueDate)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    due.setHours(0, 0, 0, 0)
    const daysUntilDue = Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
    if (daysUntilDue < 0) return 'overdue'
    if (daysUntilDue <= 7) return 'due-soon'
    return 'normal'
  }


  const handleAddSource = async (e) => {
    e.preventDefault()
    setAddingSource(true)
    
    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)
      
      const response = await fetch(apiUrl(`/projects/${id}/sources`), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newSource)
      })
      
      if (!response.ok) throw new Error('Kunde inte lägga till källa')
      
      // Reset form and close modal
      setNewSource({ title: '', type: 'link', url: '', comment: '' })
      setShowAddSourceModal(false)
      
      // Refresh data
      await fetchProject()
    } catch (err) {
      console.error('Error adding source:', err)
      alert('Kunde inte lägga till källa')
    } finally {
      setAddingSource(false)
    }
  }

  const handleEditSource = (source) => {
    setEditingSource(source)
    setNewSource({
      title: source.title || '',
      type: source.type || 'link',
      url: source.url || '',
      comment: source.comment || ''
    })
    setShowEditSourceModal(true)
  }

  const handleUpdateSource = async (e) => {
    e.preventDefault()
    setUpdatingSource(true)
    
    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)
      
      const response = await fetch(apiUrl(`/projects/${id}/sources/${editingSource.id}`), {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newSource)
      })
      
      if (!response.ok) throw new Error('Kunde inte uppdatera källa')
      
      // Reset form and close modal
      setEditingSource(null)
      setNewSource({ title: '', type: 'link', url: '', comment: '' })
      setShowEditSourceModal(false)
      
      // Refresh data
      await fetchProject()
    } catch (err) {
      console.error('Error updating source:', err)
      alert('Kunde inte uppdatera källa')
    } finally {
      setUpdatingSource(false)
    }
  }

  const handleEditNote = (note) => {
    setEditingNote(note)
    setEditNoteBody(note.masked_body || '')
    setShowEditNoteModal(true)
  }

  const handleUpdateNote = async (e) => {
    e.preventDefault()
    setUpdatingNote(true)
    
    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)
      
      const response = await fetch(apiUrl(`/projects/${id}/notes/${editingNote.id}`), {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: editingNote.title,
          body: editNoteBody
        })
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Kunde inte uppdatera anteckning')
      }
      
      // Reset and close modal
      setEditingNote(null)
      setEditNoteBody('')
      setShowEditNoteModal(false)
      
      // Refresh data
      await fetchProject()
    } catch (err) {
      console.error('Error updating note:', err)
      alert(`Kunde inte uppdatera anteckning: ${err.message}`)
    } finally {
      setUpdatingNote(false)
    }
  }

  const handleDeleteSource = async (sourceId) => {
    setDeleteConfirm({ 
      show: true, 
      type: 'source', 
      id: sourceId, 
      name: '' // Titel hämtas från state i render-lagret
    })
  }

  const handleDeleteDocument = async (e, documentId, documentName) => {
    e.stopPropagation() // Prevent navigation to document
    setDeleteConfirm({ 
      show: true, 
      type: 'document', 
      id: documentId, 
      name: documentName 
    })
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)
      
      const params = new URLSearchParams({
        include_metadata: exportSettings.includeMetadata,
        include_transcripts: exportSettings.includeTranscripts,
        include_notes: exportSettings.includeNotes
      })
      
      const response = await fetch(apiUrl(`/projects/${id}/export?${params}`), {
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      
      if (!response.ok) {
        throw new Error('Exporten misslyckades')
      }
      
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `project_${id}_export.md`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      
      setShowExportModal(false)
    } catch (err) {
      alert('Kunde inte skapa exportfilen. Försök igen.')
    } finally {
      setExporting(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteConfirm.id) return
    
    const apiBase = apiUrl('').replace(/\/api\/?$/, '')
    
    setDeleting(true)
    let success = false
    
    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)
      
      let endpoint = ''
      
      switch (deleteConfirm.type) {
        case 'document':
          endpoint = apiUrl(`/documents/${deleteConfirm.id}`)
          break
        case 'source':
          endpoint = apiUrl(`/projects/${id}/sources/${deleteConfirm.id}`)
          break
        default:
          throw new Error('Okänd typ att radera')
      }
      
      const response = await fetch(endpoint, {
        method: 'DELETE',
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      
      // 204 No Content is success, don't try to parse body
      if (!response.ok && response.status !== 204) {
        throw new Error(`Kunde inte radera (HTTP ${response.status})`)
      }
      
      success = true
      
      // Close modal first for better UX
      setDeleteConfirm({ show: false, type: null, id: null, name: '' })
      setDeleting(false)
      
      // Refresh project data
      await fetchProject()
    } catch (err) {
      console.error('Error deleting:', err)
      alert('Kunde inte radera: ' + err.message)
    } finally {
      // Only reset deleting state if delete failed
      if (!success) {
        setDeleting(false)
      }
    }
  }

  const handleStatusChange = async (newStatus) => {
    setUpdatingStatus(true)
    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)
      
      const response = await fetch(apiUrl(`/projects/${id}/status`), {
        method: 'PATCH',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ status: newStatus })
      })
      
      if (!response.ok) throw new Error('Kunde inte uppdatera status')
      
      const updatedProject = await response.json()
      setProject(updatedProject)
      await fetchProject() // Refresh events
    } catch (err) {
      console.error('Error updating status:', err)
      alert('Kunde inte uppdatera status')
    } finally {
      setUpdatingStatus(false)
    }
  }

  const getSourceTypeLabel = (type) => {
    const labels = {
      'link': 'Länk',
      'person': 'Person',
      'document': 'Dokument',
      'other': 'Övrigt'
    }
    return labels[type] || type
  }

  if (loading) return <div className="project-detail-page">Laddar...</div>
  if (error) return <div className="project-detail-page">Fel: {error}</div>
  if (!project) return <div className="project-detail-page">Projekt hittades inte</div>

  return (
    <div className="project-detail-page">
      <Link to="/projects" className="back-link">← Tillbaka till kontrollrum</Link>
      <div className="projects-header">
        <div className="project-title-section">
          <h2 className="projects-title">{project.name}</h2>
          {(() => {
            const u = getDueUrgency(project.due_date)
            if (!u.normalizedDate) return null
            return (
              <div className="project-header-due-date">
                <span className="project-due-date-muted">{u.normalizedDate}</span>
                {u.label && (
                  <Badge variant="normal" className={`deadline-badge ${u.variant}`}>
                    {u.label}
                  </Badge>
                )}
              </div>
            )
          })()}
        </div>
      </div>

      <div className="workspace-container">
        {/* Main Workspace */}
        <div className="workspace-main">
          <div className="material-section">
            {/* Toolbar - Small, secondary */}
            <div className="ingest-toolbar">
              <div className="toolbar-left">
                <div className="toolbar-group">
                  <button
                    className={`toolbar-item ${ingestMode === 'document' ? 'active' : ''}`}
                    onClick={() => setIngestMode('document')}
                    type="button"
                  >
                    <FileText size={14} />
                    <span>Dokument</span>
                  </button>
                  <button
                    className={`toolbar-item ${ingestMode === 'note' ? 'active' : ''}`}
                    onClick={() => setIngestMode('note')}
                    type="button"
                  >
                    <StickyNote size={14} />
                    <span>Anteckningar</span>
                  </button>
                  <button
                    className={`toolbar-item ${ingestMode === 'audio' ? 'active' : ''}`}
                    onClick={() => {
                      setIngestMode('audio')
                      setRecordingMode('record')
                      setMicPermissionError(null)
                    }}
                    type="button"
                  >
                    <Mic size={14} />
                    <span>Röstmemo</span>
                  </button>
                </div>
              </div>

              <div className="toolbar-right">
                <div className="toolbar-group">
                  <button
                    className="toolbar-item toolbar-item-strong"
                    onClick={() => setShowFortKnoxStation(true)}
                    type="button"
                    title="Öppna Fort Knox"
                  >
                    <Lock size={14} />
                    <span>Fort Knox</span>
                  </button>

                  <div className="toolbar-sep" aria-hidden="true" />

                  <div className="toolbar-status">
                    <label className="toolbar-status-label">Status</label>
                    <select
                      className="toolbar-status-select"
                      value={project.status}
                      onChange={(e) => handleStatusChange(e.target.value)}
                      disabled={updatingStatus}
                    >
                      <option value="research">Research</option>
                      <option value="processing">Bearbetning</option>
                      <option value="fact_check">Faktakoll</option>
                      <option value="ready">Klar</option>
                      <option value="archived">Arkiverad</option>
                    </select>
                  </div>

                  <div className="toolbar-sep" aria-hidden="true" />

                  <button
                    className="toolbar-item"
                    onClick={() => setShowEditModal(true)}
                    type="button"
                    title="Redigera projekt"
                  >
                    <Edit size={14} />
                    <span>Redigera</span>
                  </button>
                  <button
                    className="toolbar-item"
                    onClick={() => setShowExportModal(true)}
                    type="button"
                    title="Exportera projekt"
                  >
                    <FileText size={14} />
                    <span>Exportera</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Audio Recorder Card - Only when audio mode is active */}
            {ingestMode === 'audio' && (
              <div className={`audio-recorder-card ${(isRecording || recordingUploading || recordingProcessing) ? 'audio-recorder-busy' : ''}`}>
                <div className="audio-recorder-header">
                  <h3 className="audio-recorder-title">Röstmemo</h3>
                  <p className="audio-recorder-help">Spela in direkt eller ladda upp en ljudfil för transkribering.</p>
                </div>

                {/* Keep file input ALWAYS mounted so we can open the picker within the same user gesture tick */}
                <input
                  ref={audioInputRef}
                  type="file"
                  accept="audio/*"
                  onChange={handleAudioSelect}
                  style={{
                    position: 'absolute',
                    left: '-9999px',
                    width: '1px',
                    height: '1px',
                    opacity: 0
                  }}
                />

                <div className="audio-recorder-actions">
                  <button
                    className={`audio-action-btn audio-action-primary ${recordingMode === 'record' ? 'active' : ''}`}
                    onClick={() => {
                      setRecordingMode('record')
                      setMicPermissionError(null)
                    }}
                    disabled={isRecording || recordingUploading || recordingProcessing}
                  >
                    <Mic size={18} />
                    <span>Spela in</span>
                  </button>
                  <button
                    className={`audio-action-btn audio-action-secondary ${recordingMode === 'upload' ? 'active' : ''}`}
                    onClick={() => {
                      setRecordingMode('upload')
                      setMicPermissionError(null)
                      // IMPORTANT: Must be in the same user-gesture tick, otherwise browsers may block the picker.
                      audioInputRef.current?.click()
                    }}
                    disabled={isRecording || recordingUploading || recordingProcessing}
                  >
                    <Upload size={18} />
                    <span>Ladda upp fil</span>
                  </button>
                </div>

                <div className="audio-recorder-content">
                  <div className="audio-recording-container">
                {/* Recording mode */}
                {recordingMode === 'record' ? (
                  <div className="recording-controls">
                    {micPermissionError && (
                      <div className="recording-error">
                        <p>{micPermissionError}</p>
                        <button 
                          className="recording-fallback-btn"
                          onClick={() => {
                            setRecordingMode('upload')
                            setMicPermissionError(null)
                          }}
                        >
                          Byt till uppladdning
                        </button>
                      </div>
                    )}
                    {!isRecording && !recordingUploading && !recordingProcessing && !micPermissionError && (
                      <div className="audio-idle-placeholder">
                        <div className="audio-idle-waveform">
                          <div className="waveform-bar"></div>
                          <div className="waveform-bar"></div>
                          <div className="waveform-bar"></div>
                          <div className="waveform-bar"></div>
                          <div className="waveform-bar"></div>
                        </div>
                        <h4 className="audio-idle-title">Inspelning</h4>
                        <p className="audio-idle-status">Redo att spela in</p>
                        <button
                          className="record-start-btn"
                          onClick={startRecording}
                          disabled={!navigator.mediaDevices || !window.MediaRecorder}
                        >
                          <Mic size={24} />
                          <span>Starta inspelning</span>
                        </button>
                        
                        {/* Success message */}
                        {recordingSuccess && (
                          <div className="recording-success-box">
                            <p className="recording-success-text">Klart</p>
                            <Link 
                              to={`/projects/${id}/documents/${recordingSuccess.documentId}`}
                              className="recording-success-link"
                            >
                              Öppna dokument
                            </Link>
                          </div>
                        )}
                      </div>
                    )}
                    {isRecording && (
                      <div className="recording-active">
                        <div className="recording-pipeline">
                          <div className="recording-pipeline-step active">
                            <div className="pipeline-step-circle">
                              <Mic size={16} />
                            </div>
                            <span className="pipeline-step-label">Inspelning</span>
                          </div>
                          <div className="recording-pipeline-connector"></div>
                          <div className="recording-pipeline-step pending">
                            <div className="pipeline-step-circle">
                              <Upload size={16} />
                            </div>
                            <span className="pipeline-step-label">Uppladdning</span>
                          </div>
                          <div className="recording-pipeline-connector"></div>
                          <div className="recording-pipeline-step pending">
                            <div className="pipeline-step-circle">
                              <FileText size={16} />
                            </div>
                            <span className="pipeline-step-label">Transkription</span>
                          </div>
                        </div>
                        <div className="recording-indicator">
                          <div className="recording-dot"></div>
                          <span>Inspelar: {formatTime(recordingTime)}</span>
                          {recordingTime >= 30 && <span className="recording-limit"> (Max 30 sek)</span>}
                        </div>
                        <button className="record-stop-btn" onClick={stopRecording}>
                          Stoppa
                        </button>
                      </div>
                    )}
                    {(recordingUploading || recordingProcessing) && (
                      <div className="recording-status">
                        <div className="recording-pipeline">
                          <div className="recording-pipeline-step completed">
                            <div className="pipeline-step-circle">
                              <Mic size={16} />
                            </div>
                            <span className="pipeline-step-label">Inspelning</span>
                          </div>
                          <div className="recording-pipeline-connector active"></div>
                          <div className={`recording-pipeline-step ${recordingUploading ? 'active' : 'completed'}`}>
                            <div className="pipeline-step-circle">
                              <Upload size={16} />
                            </div>
                            <span className="pipeline-step-label">Uppladdning</span>
                          </div>
                          <div className={`recording-pipeline-connector ${recordingUploading ? '' : 'active'}`}></div>
                          <div className={`recording-pipeline-step ${recordingProcessing ? 'active' : 'pending'}`}>
                            <div className="pipeline-step-circle">
                              <FileText size={16} />
                            </div>
                            <span className="pipeline-step-label">Transkription</span>
                          </div>
                        </div>
                        <div className="recording-status-text">
                          {recordingUploading ? 'Laddar upp...' : 'Bearbetar transkription...'}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  /* Upload mode */
                  <>
                    {(recordingUploading || recordingProcessing) && (
                      <div
                        className={`ingest-dropzone ${recordingUploading || recordingProcessing ? 'uploading' : ''} ${isDraggingAudio ? 'dragging' : ''}`}
                        onDragOver={handleAudioDragOver}
                        onDragLeave={handleAudioDragLeave}
                        onDrop={handleAudioDrop}
                      >
                        <div className="dropzone-content">
                          <div className="dropzone-loading">
                            {recordingUploading ? 'Laddar upp ljudfil...' : 'Bearbetar ljudfil...'}
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                )}
                    
                    {/* Error message */}
                    {recordingError && (
                      <div className="recording-error">
                        <p>{recordingError}</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Primary Document Upload - Only when document mode is active - MUST be before Material List */}
            {ingestMode === 'document' && (
              <div className="document-primary-upload">
                <div 
                  className={`ingest-dropzone ${uploading ? 'uploading' : ''}`}
                  onClick={handleDropzoneClick}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.txt"
                    onChange={handleFileSelect}
                    // Some browsers block programmatic click() on display:none inputs.
                    // Keep it hidden but present in the layout tree.
                    style={{
                      position: 'absolute',
                      left: '-9999px',
                      width: '1px',
                      height: '1px',
                      opacity: 0
                    }}
                  />
                  <div className="dropzone-content">
                    {uploading ? (
                      <>
                        <div className="dropzone-loading">Laddar upp...</div>
                      </>
                    ) : (
                      <>
                        <Upload size={32} className="dropzone-icon" />
                        <p className="dropzone-text">Dra hit en fil eller klicka för att välja</p>
                        <p className="dropzone-hint">.TXT, .PDF • Max 25MB</p>
                      </>
                    )}
                  </div>
                </div>
                <p className="document-upload-help">Ladda upp dokument för automatisk bearbetning och sanering.</p>
              </div>
            )}

            {/* Material List - Documents section */}
            {ingestMode === 'document' && documents.length > 0 && (
              <div className="material-list">
                <h3 className="material-list-title">Dokument</h3>
                <div className="material-list-items">
                  {documents.map(doc => (
                    <div
                      key={doc.id}
                      className="material-list-item"
                    >
                      <div className="material-item-icon">
                        <File size={16} />
                      </div>
                      <div 
                        className="material-item-content"
                        onClick={() => navigate(`/projects/${id}/documents/${doc.id}`)}
                        style={{ cursor: 'pointer', flex: 1 }}
                      >
                        <div className="material-item-header">
                          <span className="material-item-filename">{doc.filename}</span>
                          <div className="material-item-badges">
                            <Badge variant={getClassificationVariant(doc.classification)}>
                              {getClassificationLabel(doc.classification)}
                            </Badge>
                            {doc.sanitize_level && (
                              <div className="sanitize-badge-container">
                                <Badge variant={doc.sanitize_level === 'paranoid' ? 'sensitive' : 'normal'} className="sanitize-badge">
                                  {doc.sanitize_level === 'normal' ? 'Normal' : doc.sanitize_level === 'strict' ? 'Strikt' : 'Paranoid'}
                                </Badge>
                                <div className="material-item-tooltip-container">
                                  <Info size={12} className="material-item-info-icon" />
                                  <div className="material-item-tooltip">
                                    {doc.sanitize_level === 'normal' 
                                      ? 'Normal: Standard sanering. Email, telefonnummer och personnummer maskeras automatiskt.'
                                      : doc.sanitize_level === 'strict'
                                      ? 'Strikt: Ytterligare numeriska sekvenser maskeras för extra säkerhet.'
                                      : 'Paranoid: Alla siffror och känsliga mönster maskeras. AI och export avstängda för maximal säkerhet.'}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="material-item-meta">
                          <span className="material-item-type">{doc.file_type.toUpperCase()}</span>
                          <span className="material-item-date">
                            {new Date(doc.created_at).toLocaleDateString('sv-SE')}
                          </span>
                          {doc.usage_restrictions && !doc.usage_restrictions.ai_allowed && (
                            <div className="material-item-restriction-container">
                              <span className="material-item-restriction">AI avstängt</span>
                              <div className="material-item-tooltip-container">
                                <Info size={12} className="material-item-info-icon" />
                                <div className="material-item-tooltip">
                                  Dokumentet krävde paranoid sanering. AI-funktioner är avstängda för säkerhet.
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                      <button
                        className="material-item-delete-btn"
                        onClick={(e) => handleDeleteDocument(e, doc.id, doc.filename)}
                        title="Radera dokument"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Journalist Notes View - Full view when in note mode */}
            {ingestMode === 'note' && (
              <JournalistNotes projectId={id} />
            )}
          </div>
        </div>

        {/* Sidebar - Källor & Anteckningar */}
        <div className="workspace-sidebar">
          <div className="sidebar-section">
            <div className="sidebar-section-header">
              <h3 className="sidebar-section-title">Källor</h3>
              <button 
                className="btn-add-source" 
                onClick={() => setShowAddSourceModal(true)}
                title="Lägg till källa"
              >
                + Lägg till
              </button>
            </div>

            {sources.length === 0 && projectNotes.length === 0 ? (
              <p className="sources-empty">Inga källor tillagda</p>
            ) : (
              <div className="sources-list">
                {/* Show ProjectNotes as sources */}
                {projectNotes.map(note => (
                  <div key={`note-${note.id}`} className="source-item">
                    <div className="source-header">
                      <span className="source-type-badge">Anteckning</span>
                      <div className="source-actions">
                        <button 
                          className="source-edit-btn"
                          onClick={() => handleEditNote(note)}
                          title="Redigera anteckning"
                        >
                          <Edit size={14} />
                        </button>
                      </div>
                    </div>
                    <div className="source-title">{note.title || 'Anteckning'}</div>
                    {note.masked_body && (
                      <div className="source-comment" style={{ 
                        maxHeight: '150px', 
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'pre-wrap',
                        fontSize: 'var(--font-size-xs)',
                        fontFamily: 'monospace'
                      }}>
                        {note.masked_body.substring(0, 200)}{note.masked_body.length > 200 ? '...' : ''}
                      </div>
                    )}
                    <div className="source-date">
                      {new Date(note.created_at).toLocaleDateString('sv-SE')}
                    </div>
                  </div>
                ))}
                {/* Show actual sources */}
                {sources.map(source => (
                  <div key={source.id} className="source-item">
                    <div className="source-header">
                      <span className="source-type-badge">
                        {getSourceTypeLabel(source.type)}
                      </span>
                      <div className="source-actions">
                        <button 
                          className="source-edit-btn"
                          onClick={() => handleEditSource(source)}
                          title="Redigera källa"
                        >
                          <Edit size={14} />
                        </button>
                        <button 
                          className="source-delete-btn"
                          onClick={() => handleDeleteSource(source.id)}
                          title="Radera källa"
                        >
                          ×
                        </button>
                      </div>
                    </div>
                    <div className="source-title">{source.title}</div>
                    {source.url && (
                      <div className="source-url">
                        <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-link">
                          {source.url}
                        </a>
                      </div>
                    )}
                    {source.comment && (
                      <div className="source-comment">{source.comment}</div>
                    )}
                    <div className="source-date">
                      {new Date(source.created_at).toLocaleDateString('sv-SE')}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
      
      {/* Edit Project Modal (includes delete functionality) */}
      <Modal isOpen={showEditModal} onClose={() => setShowEditModal(false)} title="Redigera projekt">
        <CreateProject
          project={project}
          onClose={() => setShowEditModal(false)}
          onSuccess={async (updatedProject) => {
            setProject(updatedProject)
            setShowEditModal(false)
            // Refresh project data to ensure UI is up to date
            await fetchProject()
          }}
        />
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal 
        isOpen={deleteConfirm.show} 
        onClose={() => !deleting && setDeleteConfirm({ show: false, type: null, id: null, name: '' })}
      >
        <div className="delete-confirmation-modal">
          <div className="delete-confirmation-icon">
            <Trash2 size={48} />
          </div>
          <h3 className="delete-confirmation-title">
            Radera {deleteConfirm.type === 'document' ? 'dokument' : 'källa'}?
          </h3>
          <p className="delete-confirmation-text">
            Är du säker på att du vill radera <strong>{
              deleteConfirm.type === 'source' 
                ? sources.find(s => s.id === deleteConfirm.id)?.title || 'denna källa'
                : deleteConfirm.name
            }</strong>?
          </p>
          <p className="delete-confirmation-warning">
            Denna åtgärd kan inte ångras.
          </p>
          <div className="delete-confirmation-actions">
            <Button 
              type="button" 
              variant="secondary" 
              onClick={() => setDeleteConfirm({ show: false, type: null, id: null, name: '' })}
              disabled={deleting}
            >
              Avbryt
            </Button>
            <Button 
              type="button" 
              variant="error" 
              onClick={confirmDelete}
              disabled={deleting}
            >
              {deleting ? 'Raderar...' : 'Radera permanent'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Add Source Modal */}
      <Modal isOpen={showAddSourceModal} onClose={() => setShowAddSourceModal(false)} title="Lägg till källa">
        <form onSubmit={handleAddSource} className="add-source-form">
          <div className="form-group">
            <label htmlFor="source-title">Titel *</label>
            <input
              id="source-title"
              type="text"
              value={newSource.title}
              onChange={(e) => setNewSource({...newSource, title: e.target.value})}
              maxLength={200}
              required
              placeholder="T.ex. 'Regeringens pressmeddelande'"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="source-type">Typ *</label>
            <select
              id="source-type"
              value={newSource.type}
              onChange={(e) => setNewSource({...newSource, type: e.target.value})}
              required
            >
              <option value="link">Länk</option>
              <option value="person">Person</option>
              <option value="document">Dokument</option>
              <option value="other">Övrigt</option>
            </select>
          </div>
          
          <div className="form-group">
            <label htmlFor="source-url">URL</label>
            <input
              id="source-url"
              type="url"
              value={newSource.url}
              onChange={(e) => setNewSource({...newSource, url: e.target.value})}
              placeholder="https://..."
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="source-comment">Kommentar</label>
            <textarea
              id="source-comment"
              value={newSource.comment}
              onChange={(e) => setNewSource({...newSource, comment: e.target.value})}
              maxLength={500}
              rows={3}
              placeholder="Valfri beskrivning"
            />
          </div>
          
          <div className="modal-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowAddSourceModal(false)}
              disabled={addingSource}
            >
              Avbryt
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={addingSource}
            >
              {addingSource ? 'Lägger till...' : 'Lägg till källa'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Note Modal */}
      <Modal isOpen={showEditNoteModal} onClose={() => setShowEditNoteModal(false)} title="Redigera anteckning">
        <form onSubmit={handleUpdateNote} className="add-source-form">
          <div className="form-group">
            <label htmlFor="edit-note-title">Titel</label>
            <input
              id="edit-note-title"
              type="text"
              value={editingNote?.title || ''}
              onChange={(e) => setEditingNote({...editingNote, title: e.target.value})}
              maxLength={200}
              placeholder="Valfri titel"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="edit-note-body">Innehåll *</label>
            <textarea
              id="edit-note-body"
              value={editNoteBody}
              onChange={(e) => setEditNoteBody(e.target.value)}
              required
              rows={15}
              placeholder="Anteckningens innehåll..."
              style={{ fontFamily: 'monospace', fontSize: '0.9em' }}
            />
          </div>
          
          <div className="modal-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setShowEditNoteModal(false)
                setEditingNote(null)
                setEditNoteBody('')
              }}
              disabled={updatingNote}
            >
              Avbryt
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={updatingNote}
            >
              {updatingNote ? 'Uppdaterar...' : 'Spara ändringar'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Source Modal */}
      <Modal isOpen={showEditSourceModal} onClose={() => setShowEditSourceModal(false)} title="Redigera källa">
        <form onSubmit={handleUpdateSource} className="add-source-form">
          <div className="form-group">
            <label htmlFor="edit-source-title">Titel *</label>
            <input
              id="edit-source-title"
              type="text"
              value={newSource.title}
              onChange={(e) => setNewSource({...newSource, title: e.target.value})}
              maxLength={200}
              required
              placeholder="T.ex. 'Regeringens pressmeddelande'"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="edit-source-type">Typ *</label>
            <select
              id="edit-source-type"
              value={newSource.type}
              onChange={(e) => setNewSource({...newSource, type: e.target.value})}
              required
            >
              <option value="link">Länk</option>
              <option value="person">Person</option>
              <option value="document">Dokument</option>
              <option value="other">Övrigt</option>
            </select>
          </div>
          
          <div className="form-group">
            <label htmlFor="edit-source-url">URL</label>
            <input
              id="edit-source-url"
              type="url"
              value={newSource.url}
              onChange={(e) => setNewSource({...newSource, url: e.target.value})}
              placeholder="https://..."
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="edit-source-comment">Kommentar</label>
            <textarea
              id="edit-source-comment"
              value={newSource.comment}
              onChange={(e) => setNewSource({...newSource, comment: e.target.value})}
              maxLength={500}
              rows={3}
              placeholder="Valfri beskrivning"
            />
          </div>
          
          <div className="modal-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setShowEditSourceModal(false)
                setEditingSource(null)
                setNewSource({ title: '', type: 'link', url: '', comment: '' })
              }}
              disabled={updatingSource}
            >
              Avbryt
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={updatingSource}
            >
              {updatingSource ? 'Uppdaterar...' : 'Spara ändringar'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Export Modal */}
      <Modal isOpen={showExportModal} onClose={() => setShowExportModal(false)} title="Exportera projekt">
        <div className="export-modal">
            <p className="export-description">
              Ladda ner en Markdown-fil som kan lämnas vidare eller arkiveras.
            </p>
            
            <h3 className="export-section-title">Innehåll</h3>
            
            <div className="export-toggles">
              <div className="export-toggle-item">
                <label>
                  <input 
                    type="checkbox"
                    checked={exportSettings.includeMetadata}
                    onChange={(e) => setExportSettings({...exportSettings, includeMetadata: e.target.checked})}
                  />
                  <div className="export-toggle-text">
                    <span className="export-toggle-label">Inkludera metadata</span>
                    <span className="export-toggle-help">Projektinfo, status och källor.</span>
                  </div>
                </label>
              </div>
              
              <div className="export-toggle-item">
                <label>
                  <input 
                    type="checkbox"
                    checked={exportSettings.includeTranscripts}
                    onChange={(e) => setExportSettings({...exportSettings, includeTranscripts: e.target.checked})}
                  />
                  <div className="export-toggle-text">
                    <span className="export-toggle-label">Inkludera röstmemo och transkript</span>
                    <span className="export-toggle-help">Sanerat material. Endast om du aktivt väljer det.</span>
                  </div>
                </label>
              </div>
              
              <div className="export-toggle-item export-toggle-sensitive">
                <label>
                  <input 
                    type="checkbox"
                    checked={exportSettings.includeNotes}
                    onChange={(e) => setExportSettings({...exportSettings, includeNotes: e.target.checked})}
                  />
                  <div className="export-toggle-text">
                    <span className="export-toggle-label">Inkludera privata anteckningar</span>
                    <span className="export-toggle-help export-toggle-help-warning">Privat material. Ingår inte som standard.</span>
                  </div>
                </label>
              </div>
            </div>
            
            <p className="export-privacy-notice">
              <strong>Integritet:</strong> Export påverkar inte originalet. Systemets loggar och händelser innehåller aldrig innehåll, endast metadata.
            </p>
            
            <div className="export-modal-actions">
              <button 
                className="btn-secondary"
                onClick={() => setShowExportModal(false)}
                disabled={exporting}
              >
                Avbryt
              </button>
              <button 
                className="btn-primary"
                onClick={handleExport}
                disabled={exporting}
              >
                {exporting ? 'Exporterar…' : 'Ladda ner'}
              </button>
            </div>
          </div>
      </Modal>

      <Modal
        isOpen={showTranscriptModal}
        onClose={() => setShowTranscriptModal(false)}
        title="Röstmemo transkriberat"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
          <p style={{ color: 'var(--color-text-muted)', margin: 0 }}>
            Klart. Röstmemon sparas som ett dokument i projektet.
          </p>
          {transcriptPreviewLoading ? (
            <p style={{ margin: 0 }}>Hämtar förhandsvisning…</p>
          ) : transcriptPreviewError ? (
            <p style={{ margin: 0 }}>{transcriptPreviewError}</p>
          ) : (
            <div className="transcript-preview-box">
              <pre className="transcript-preview-text">{transcriptPreview || '—'}</pre>
            </div>
          )}
          <div style={{ display: 'flex', gap: 'var(--spacing-sm)', justifyContent: 'flex-end' }}>
            <Button variant="secondary" onClick={() => setShowTranscriptModal(false)}>
              Stäng
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                if (transcriptDocId) {
                  setShowTranscriptModal(false)
                  navigate(`/projects/${id}/documents/${transcriptDocId}`)
                }
              }}
              disabled={!transcriptDocId}
            >
              Öppna dokument
            </Button>
          </div>
        </div>
      </Modal>

      {/* Fort Knox Station */}
      {showFortKnoxStation && (
        <FortKnoxStation
          projectId={id}
          onClose={() => setShowFortKnoxStation(false)}
        />
      )}
    </div>
  )
}

export default ProjectDetail
