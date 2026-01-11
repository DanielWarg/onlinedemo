import { useState, useEffect } from 'react'
import { Lock, CheckCircle, XCircle, AlertCircle, Loader, FileText, StickyNote, Edit, X } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Select } from '../ui/Select'
import { Modal } from '../ui/Modal'
import { apiUrl } from '../lib/api'
import { pollJob } from '../lib/jobs'
import './FortKnoxStation.css'

function FortKnoxStation({ projectId, onClose, embedded = false }) {
  const [activeTab, setActiveTab] = useState('internal')
  const [policyId, setPolicyId] = useState('internal')
  const [templateId, setTemplateId] = useState('weekly')
  
  // Internal state (existing compile)
  const [loading, setLoading] = useState(false)
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)
  const [lastReportId, setLastReportId] = useState(null)
  const [isCacheHit, setIsCacheHit] = useState(false)
  
  // External state (new station)
  const [snapshot, setSnapshot] = useState(null)
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const [selection, setSelection] = useState({ include: [], exclude: [] })
  const [blockingItems, setBlockingItems] = useState(new Set())
  const [fixingItems, setFixingItems] = useState(new Set())
  const [rowErrors, setRowErrors] = useState(new Map()) // key -> {code, message}
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [editText, setEditText] = useState('')
  const [editLevel, setEditLevel] = useState('normal')
  const [saving, setSaving] = useState(false)
  const [savingReportDoc, setSavingReportDoc] = useState(false)
  const [savedReportDoc, setSavedReportDoc] = useState(null) // {id, filename}

  const username = 'admin'
  const password = 'password'
  const auth = btoa(`${username}:${password}`)

  // När projekt byts i Fort Knox-sidan måste vi nollställa intern state,
  // annars ser det ut som att dropdown inte gör något (gammalt snapshot/rapport ligger kvar).
  useEffect(() => {
    // Reset internal compile state
    setLoading(false)
    setReport(null)
    setError(null)
    setLastReportId(null)
    setIsCacheHit(false)

    // Reset external station state
    setSnapshot(null)
    setSnapshotLoading(false)
    setSelection({ include: [], exclude: [] })
    setBlockingItems(new Set())
    setFixingItems(new Set())
    setRowErrors(new Map())
    setShowEditModal(false)
    setEditingItem(null)
    setEditText('')
    setEditLevel('normal')
    setSaving(false)
    setSavingReportDoc(false)
    setSavedReportDoc(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  // Load snapshot when External tab is active
  useEffect(() => {
    if (activeTab === 'external' && projectId && !snapshot) {
      loadSnapshot()
    }
  }, [activeTab, projectId])

  const loadSnapshot = async () => {
    setSnapshotLoading(true)
    try {
      const response = await fetch(apiUrl(`/projects/${projectId}/export_snapshot`), {
        headers: { 'Authorization': `Basic ${auth}` }
      })
      if (response.ok) {
        const data = await response.json()
        setSnapshot(data)
        // Default: all items included
        const include = (data.input_manifest || []).map(item => ({
          type: item.type,
          id: item.id
        }))
        setSelection({ include, exclude: [] })
      } else {
        console.error('Failed to load snapshot')
      }
    } catch (err) {
      console.error('Error loading snapshot:', err)
    } finally {
      setSnapshotLoading(false)
    }
  }

  const parseKnoxError = (payload) => {
    if (Array.isArray(payload?.detail)) {
      const reasons = payload.detail.map(err => {
        const loc = err.loc ? err.loc.join('.') : 'unknown'
        const msg = err.msg || 'Validation error'
        return `${loc}: ${msg}`
      })
      return { error_code: 'VALIDATION_ERROR', reasons, detail: payload }
    }
    if (payload?.detail?.error_code) {
      return payload.detail
    }
    if (payload?.error_code) {
      return payload
    }
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

  // Parse blocking reasons to items
  const parseBlockingReasons = (reasons) => {
    const items = new Set()
    reasons.forEach(reason => {
      const docMatch = reason.match(/^document_(\d+)_sanitize_level_too_low$/)
      const noteMatch = reason.match(/^note_(\d+)_sanitize_level_too_low$/)
      if (docMatch) {
        items.add(`document_${docMatch[1]}`)
      } else if (noteMatch) {
        items.add(`note_${noteMatch[1]}`)
      }
    })
    return items
  }

  const humanizeReason = (r) => {
    // Ingen datum-gate längre: datum maskas i pipeline
    return r
  }

  // Update blocking items when error changes
  useEffect(() => {
    if (error && status === 'BLOCKED') {
      const blocked = parseBlockingReasons(error.reasons || [])
      setBlockingItems(blocked)
    } else {
      setBlockingItems(new Set())
    }
  }, [error, status])

  const handleCompileInternal = async () => {
    setLoading(true)
    setError(null)
    const controller = new AbortController()
    // Lokal LLM kan ta tid. Backend default är 180s (FORTKNOX_REMOTE_TIMEOUT).
    const timeoutId = setTimeout(() => controller.abort(), 180000)

    try {
      const body = {
        project_id: parseInt(projectId),
        policy_id: policyId,
        template_id: templateId
      }

      // Försök async jobs först (demo-safe: backend svarar 409 om avstängt)
      let response = await fetch(apiUrl('/fortknox/compile/jobs'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${auth}`
        },
        body: JSON.stringify(body)
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
        const reportRes = await fetch(apiUrl(`/fortknox/reports/${reportId}`), {
          headers: { 'Authorization': `Basic ${auth}` }
        })
        if (!reportRes.ok) throw new Error(`HTTP ${reportRes.status}`)
        const data = await reportRes.json()
        const cacheHit = lastReportId !== null && data.id === lastReportId
        setIsCacheHit(cacheHit)
        setReport(data)
        setError(null)
        setLastReportId(data.id)
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
          body: JSON.stringify(body),
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
      } else {
        const errorData = await response.json().catch(async () => {
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

  const handleCompileExternal = async () => {
    setLoading(true)
    setError(null)
    const controller = new AbortController()
    // Lokal LLM kan ta tid. Backend default är 180s (FORTKNOX_REMOTE_TIMEOUT).
    const timeoutId = setTimeout(() => controller.abort(), 180000)

    try {
      const body = {
        project_id: parseInt(projectId),
        policy_id: 'external',
        template_id: templateId,
        selection: selection,
        snapshot_mode: true
      }

      // Försök async jobs först (demo-safe: backend svarar 409 om avstängt)
      let response = await fetch(apiUrl('/fortknox/compile/jobs'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${auth}`
        },
        body: JSON.stringify(body)
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
        const reportRes = await fetch(apiUrl(`/fortknox/reports/${reportId}`), {
          headers: { 'Authorization': `Basic ${auth}` }
        })
        if (!reportRes.ok) throw new Error(`HTTP ${reportRes.status}`)
        const data = await reportRes.json()
        const cacheHit = lastReportId !== null && data.id === lastReportId
        setIsCacheHit(cacheHit)
        setReport(data)
        setError(null)
        setLastReportId(data.id)
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
          body: JSON.stringify(body),
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
      } else {
        const errorData = await response.json().catch(async () => {
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

  const toggleItemSelection = (item) => {
    const key = `${item.type}_${item.id}`
    const isIncluded = selection.include.some(i => i.type === item.type && i.id === item.id)
    
    if (isIncluded) {
      // Remove from include, add to exclude
      setSelection(prev => ({
        include: prev.include.filter(i => !(i.type === item.type && i.id === item.id)),
        exclude: [...prev.exclude.filter(i => !(i.type === item.type && i.id === item.id)), { type: item.type, id: item.id }]
      }))
    } else {
      // Remove from exclude, add to include
      setSelection(prev => ({
        include: [...prev.include.filter(i => !(i.type === item.type && i.id === item.id)), { type: item.type, id: item.id }],
        exclude: prev.exclude.filter(i => !(i.type === item.type && i.id === item.id))
      }))
    }
  }

  const handleAutofixAll = async () => {
    const itemsToFix = Array.from(blockingItems)
    setFixingItems(new Set(itemsToFix))
    
    try {
      const promises = itemsToFix.map(async (key) => {
        const [type, id] = key.split('_')
        const level = policyId === 'external' ? 'strict' : 'strict'
        
        if (type === 'document') {
          const response = await fetch(apiUrl(`/documents/${id}/sanitize-level`), {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Basic ${auth}`
            },
            body: JSON.stringify({ level })
          })
          if (!response.ok) {
            const err = await response.json().catch(() => ({}))
            const parsed = parseKnoxError(err)
            // Handle ORIGINAL_MISSING gracefully (FastAPI kan wrappa i detail)
            if (parsed?.error_code === 'ORIGINAL_MISSING') {
              setRowErrors(prev => new Map(prev).set(`document_${id}`, { code: 'ORIGINAL_MISSING', message: (err?.detail?.message || err?.message || 'Original saknas') }))
              return
            }
            throw new Error(`Kunde inte åtgärda dokument ${id}: ${parsed?.error_code || 'OKÄNT_FEL'}`)
          }
        } else if (type === 'note') {
          const response = await fetch(apiUrl(`/projects/${projectId}/notes/${id}/sanitize-level`), {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Basic ${auth}`
            },
            body: JSON.stringify({ level })
          })
          if (!response.ok) {
            const err = await response.json().catch(() => ({}))
            const parsed = parseKnoxError(err)
            throw new Error((parsed?.detail || parsed?.error_code) || `Kunde inte åtgärda anteckning ${id}`)
          }
        }
      })
      
      await Promise.all(promises)
      // Reload snapshot and re-compile
      await loadSnapshot()
      setTimeout(() => handleCompileExternal(), 500)
    } catch (err) {
      console.error('Autofix failed:', err)
    } finally {
      setFixingItems(new Set())
    }
  }

  const handleAutofixItem = async (item) => {
    const key = `${item.type}_${item.id}`
    setFixingItems(new Set([key]))
    
    try {
      const level = policyId === 'external' ? 'strict' : 'strict'
      
      if (item.type === 'document') {
        const response = await fetch(apiUrl(`/documents/${item.id}/sanitize-level`), {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Basic ${auth}`
          },
          body: JSON.stringify({ level })
        })
        if (!response.ok) {
          const err = await response.json().catch(() => ({}))
          const parsed = parseKnoxError(err)
          if (parsed?.error_code === 'ORIGINAL_MISSING') {
            setRowErrors(prev => new Map(prev).set(`document_${item.id}`, { code: 'ORIGINAL_MISSING', message: (err?.detail?.message || err?.message || 'Original saknas') }))
            return
          }
          throw new Error(`Kunde inte åtgärda dokument ${item.id}: ${parsed?.error_code || 'OKÄNT_FEL'}`)
        }
      } else if (item.type === 'note') {
        const response = await fetch(apiUrl(`/projects/${projectId}/notes/${item.id}/sanitize-level`), {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Basic ${auth}`
          },
          body: JSON.stringify({ level })
        })
        if (!response.ok) {
          const err = await response.json().catch(() => ({}))
          const parsed = parseKnoxError(err)
          throw new Error((parsed?.detail || parsed?.error_code) || `Kunde inte åtgärda anteckning ${item.id}`)
        }
      }
      
      // Reload snapshot and re-compile
      await loadSnapshot()
      setTimeout(() => handleCompileExternal(), 500)
    } catch (err) {
      console.error('Autofix item failed:', err)
    } finally {
      setFixingItems(new Set())
    }
  }

  const handleEditItem = async (item) => {
    setEditingItem(item)
    setEditLevel(item.sanitize_level || 'normal')
    setSaving(true)
    
    try {
      // Fetch full item data
      if (item.type === 'document') {
        const response = await fetch(apiUrl(`/documents/${item.id}`), {
          headers: { 'Authorization': `Basic ${auth}` }
        })
        if (response.ok) {
          const data = await response.json()
          setEditText(data.masked_text || '')
        }
      } else if (item.type === 'note') {
        // OBS: GET-endpointen för ProjectNote är /api/notes/{note_id} (inte /api/projects/{project}/notes/{note})
        const response = await fetch(apiUrl(`/notes/${item.id}`), {
          headers: { 'Authorization': `Basic ${auth}` }
        })
        if (response.ok) {
          const data = await response.json()
          setEditText(data.masked_body || '')
        }
      }
    } catch (err) {
      console.error('Failed to fetch item:', err)
    } finally {
      setSaving(false)
      setShowEditModal(true)
    }
  }

  const handleSaveEdit = async () => {
    if (!editingItem) return
    setSaving(true)
    
    try {
      // Update document/note with new text and level
      if (editingItem.type === 'document') {
        // Update masked_text
        const updateResponse = await fetch(apiUrl(`/documents/${editingItem.id}`), {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Basic ${auth}`
          },
          body: JSON.stringify({ masked_text: editText })
        })
        if (!updateResponse.ok) throw new Error('Kunde inte uppdatera dokument')
        
        // Bump sanitize level if changed
        if (editLevel !== editingItem.sanitize_level && (editLevel === 'strict' || editLevel === 'paranoid')) {
          const bumpResponse = await fetch(apiUrl(`/documents/${editingItem.id}/sanitize-level`), {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Basic ${auth}`
            },
            body: JSON.stringify({ level: editLevel })
          })
          if (!bumpResponse.ok) throw new Error('Kunde inte höja maskeringsnivå')
        }
      } else if (editingItem.type === 'note') {
        // Update note body
        const updateResponse = await fetch(apiUrl(`/projects/${projectId}/notes/${editingItem.id}`), {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Basic ${auth}`
          },
          body: JSON.stringify({ body: editText })
        })
        if (!updateResponse.ok) throw new Error('Kunde inte uppdatera anteckning')
        
        // Bump sanitize level if changed
        if (editLevel !== editingItem.sanitize_level && (editLevel === 'strict' || editLevel === 'paranoid')) {
          const bumpResponse = await fetch(apiUrl(`/projects/${projectId}/notes/${editingItem.id}/sanitize-level`), {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Basic ${auth}`
            },
            body: JSON.stringify({ level: editLevel })
          })
          if (!bumpResponse.ok) throw new Error('Kunde inte höja maskeringsnivå')
        }
      }
      
      // Reload snapshot and re-compile
      setShowEditModal(false)
      setEditingItem(null)
      await loadSnapshot()
      setTimeout(() => handleCompileExternal(), 500)
    } catch (err) {
      console.error('Save failed:', err)
      alert(`Kunde inte spara: ${err.message}`)
    } finally {
      setSaving(false)
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
      } else if (trimmed.startsWith('### ')) {
        if (currentParagraph.length > 0) {
          elements.push(<p key={`p-${index}`} className="fortknox-markdown-p">{currentParagraph.join(' ')}</p>)
          currentParagraph = []
        }
        elements.push(<h3 key={`h3-${index}`} className="fortknox-markdown-h3">{trimmed.substring(4)}</h3>)
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
    
    return <div className="fortknox-markdown">{elements}</div>
  }

  if (embedded) {
    return (
      <div className="fortknox-station-embedded-root">
        <div className="fortknox-station-drawer fortknox-station-drawer-embedded">
          <div className="fortknox-station-header">
            <div className="fortknox-station-title">
              <Lock size={24} />
              <h2>Fort Knox</h2>
            </div>
          </div>

          <div className="fortknox-station-tabs">
            <button
              className={`fortknox-tab ${activeTab === 'internal' ? 'active' : ''}`}
              onClick={() => setActiveTab('internal')}
            >
              Intern
            </button>
            <button
              className={`fortknox-tab ${activeTab === 'external' ? 'active' : ''}`}
              onClick={() => setActiveTab('external')}
            >
              Extern
            </button>
          </div>
          
          <div className="fortknox-station-explain">
            {activeTab === 'internal' ? (
              <p>
                <strong>Intern</strong>: redaktionell brief för internt arbete. Innehållet är sanerat men kan vara mer detaljerat.
                <span className="fortknox-station-explain-muted"> Rapport kan ta 1–3 min att generera (lokal modell).</span>
              </p>
            ) : (
              <p>
                <strong>Extern</strong>: strikt policy för extern sammanställning. Underlaget måste vara <strong>strict</strong> eller högre och får inte återskapa citat eller identifierande formuleringar.
                <span className="fortknox-station-explain-muted"> Rapport kan ta 1–3 min att generera (lokal modell).</span>
              </p>
            )}
          </div>

          {activeTab === 'internal' && (
            <div className="fortknox-station-content">
              <div className="fortknox-station-controls">
                <Select
                  value={templateId}
                  onChange={(e) => setTemplateId(e.target.value)}
                  disabled={loading}
                >
                  <option value="weekly">Weekly</option>
                </Select>
                <Button
                  variant="primary"
                  onClick={handleCompileInternal}
                  disabled={loading}
                >
                  {loading ? 'Kompilerar...' : 'Kompilera rapport'}
                </Button>
                {loading && (
                  <span className="fortknox-inline-hint">
                    Lokal AI arbetar – kan ta upp till 3 min.
                  </span>
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

              {error && !loading && (
                <div className="fortknox-error-card">
                  <h4>Fel</h4>
                  <p>{error.error_code}</p>
                  {error.reasons && error.reasons.length > 0 && (
                    <ul>
                      {error.reasons.slice(0, 5).map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {report && !loading && (
                <div className="fortknox-report-container">
                  <div className="fortknox-report-header">
                    <CheckCircle size={18} />
                    <span>Rapport genererad</span>
                  </div>
                  <div className="fortknox-report-actions">
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
                  {renderMarkdown(report.rendered_markdown)}
                  {report.input_fingerprint && (
                    <div className="fortknox-audit-footer">
                      <div>Fingerprint: {report.input_fingerprint.substring(0, 16)}...</div>
                      <div>Policy: {report.policy_id} v{report.policy_version}</div>
                      <div>Ruleset: {report.ruleset_hash}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'external' && (
            <div className="fortknox-station-external">
              <div className="fortknox-station-selection">
                <h3>Underlag</h3>
                {snapshotLoading ? (
                  <div className="fortknox-loading">
                    <Loader className="spinner" />
                  </div>
                ) : snapshot ? (
                  <div className="fortknox-item-list">
                    {(snapshot.input_manifest || []).map((item) => {
                      const key = `${item.type}_${item.id}`
                      const isIncluded = selection.include.some(i => i.type === item.type && i.id === item.id)
                      const isBlocking = blockingItems.has(key)
                      const hasDatetimeMasked = item.datetime_masked === true
                      const isFixing = fixingItems.has(key)
                      const rowErr = rowErrors.get(key)
                      
                      return (
                        <div key={key} className={`fortknox-item-row ${isBlocking ? 'blocking' : ''}`}>
                          <input
                            type="checkbox"
                            checked={isIncluded}
                            onChange={() => toggleItemSelection(item)}
                          />
                          <div className="fortknox-item-info">
                            <span className="fortknox-item-type">{item.type === 'document' ? <FileText size={14} /> : <StickyNote size={14} />}</span>
                            <Badge variant="normal">
                              {item.origin === 'scout' ? 'AUTO' : 'MANUAL'}
                            </Badge>
                            <span className="fortknox-item-title">{item.title}</span>
                            <Badge variant={isBlocking ? 'sensitive' : 'normal'}>
                              {item.sanitize_level}
                            </Badge>
                            {hasDatetimeMasked && <Badge variant="normal">Datum maskat</Badge>}
                            {isBlocking && <Badge variant="sensitive">BLOCKERAR</Badge>}
                          </div>
                          <div className="fortknox-item-actions">
                            {isBlocking && !rowErr && (
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => handleAutofixItem(item)}
                                disabled={isFixing}
                              >
                                {isFixing ? 'Fixing...' : 'Autofixa'}
                              </Button>
                            )}
                            {rowErr && rowErr.code === 'ORIGINAL_MISSING' && (
                              <>
                                <span className="row-inline-help">Original saknas. Välj “Exkludera”.</span>
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  onClick={() => toggleItemSelection(item)}
                                >
                                  Exkludera
                                </Button>
                              </>
                            )}
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => handleEditItem(item)}
                            >
                              <Edit size={14} />
                            </Button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div>Inget underlag hittat</div>
                )}
              </div>

              <div className="fortknox-station-result">
                <div className="fortknox-station-controls">
                  <Select
                    value={templateId}
                    onChange={(e) => setTemplateId(e.target.value)}
                    disabled={loading}
                  >
                    <option value="weekly">Weekly</option>
                  </Select>
                  {blockingItems.size > 0 && (
                    <Button
                      variant="secondary"
                      onClick={handleAutofixAll}
                      disabled={fixingItems.size > 0}
                    >
                      Autofixa blockerande ({blockingItems.size})
                    </Button>
                  )}
                  <Button
                    variant="primary"
                    onClick={handleCompileExternal}
                    disabled={loading}
                  >
                    {loading ? 'Kompilerar...' : 'Kompilera Extern'}
                  </Button>
                  {loading && (
                    <span className="fortknox-inline-hint">
                      Lokal AI arbetar – kan ta upp till 3 min.
                    </span>
                  )}
                </div>

                {error && !loading && status === 'BLOCKED' && (
                  <div className="fortknox-fix-center">
                    <h4>Extern kräver åtgärd (ingen data har skickats)</h4>
                    <ul>
                      {error.reasons?.slice(0, 5).map((r, i) => (
                        <li key={i}>{humanizeReason(r)}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {error && !loading && status === 'ERROR' && (
                  <div className="fortknox-error-card">
                    <h4>
                      {error.error_code === 'EMPTY_INPUT_SET' 
                        ? 'Tomt underlag'
                        : 'Tekniskt fel'}
                    </h4>
                    <p>
                      {error.error_code === 'EMPTY_INPUT_SET'
                        ? 'Du har exkluderat allt underlag. Välj minst ett dokument eller en anteckning.'
                        : error.detail || 'Okänt fel'}
                    </p>
                  </div>
                )}

                {loading && (
                  <div className="fortknox-loading">
                    <div className="fortknox-skeleton shimmer"></div>
                    <div className="fortknox-skeleton shimmer"></div>
                    <div className="fortknox-loading-hint">Detta kan ta 1–3 min (lokal modell).</div>
                  </div>
                )}

                {report && !loading && (
                  <div className="fortknox-report-container">
                    <div className="fortknox-report-header">
                      <CheckCircle size={18} />
                      <span>Rapport genererad</span>
                    </div>
                    <div className="fortknox-report-actions">
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
                    {renderMarkdown(report.rendered_markdown)}
                    {report.input_fingerprint && (
                      <div className="fortknox-audit-footer">
                        <div>Fingerprint: {report.input_fingerprint.substring(0, 16)}...</div>
                        <div>Policy: {report.policy_id} v{report.policy_version}</div>
                        <div>Ruleset: {report.ruleset_hash}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {showEditModal && editingItem && (
            <Modal
              isOpen={showEditModal}
              onClose={() => setShowEditModal(false)}
              title={`Redigera ${editingItem.type === 'document' ? 'dokument' : 'anteckning'}`}
              contentClassName="modal-wide"
            >
              <div className="fortknox-edit-modal">
                {saving && editText === '' ? (
                  <div className="fortknox-loading">
                    <Loader className="spinner" />
                    <span>Laddar innehåll...</span>
                  </div>
                ) : (
                  <>
                    <div className="form-group">
                      <label>Sanitize Level</label>
                      <Select
                        value={editLevel}
                        onChange={(e) => setEditLevel(e.target.value)}
                      >
                        <option value="normal">Normal</option>
                        <option value="strict">Strict (rekommenderas för Extern)</option>
                        <option value="paranoid">Paranoid</option>
                      </Select>
                    </div>
                    <div className="form-group">
                      <label>Innehåll (maskat/sanerat)</label>
                      <textarea
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        rows={15}
                        placeholder="Redigera innehållet här..."
                      />
                    </div>
                    <div className="fortknox-edit-actions">
                      <Button onClick={() => {
                        setShowEditModal(false)
                        setEditingItem(null)
                        setEditText('')
                      }}>Avbryt</Button>
                      <Button variant="primary" onClick={handleSaveEdit} disabled={saving}>
                        {saving ? 'Sparar...' : 'Spara och kompilera'}
                      </Button>
                    </div>
                  </>
                )}
              </div>
            </Modal>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="fortknox-station-overlay" onClick={onClose}>
      <div className="fortknox-station-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="fortknox-station-header">
          <div className="fortknox-station-title">
            <Lock size={24} />
            <h2>Fort Knox</h2>
          </div>
          <button className="fortknox-station-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="fortknox-station-tabs">
          <button
            className={`fortknox-tab ${activeTab === 'internal' ? 'active' : ''}`}
            onClick={() => setActiveTab('internal')}
          >
            Intern
          </button>
          <button
            className={`fortknox-tab ${activeTab === 'external' ? 'active' : ''}`}
            onClick={() => setActiveTab('external')}
          >
            Extern
          </button>
        </div>

        {activeTab === 'internal' && (
          <div className="fortknox-station-content">
            <div className="fortknox-station-controls">
              <Select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                disabled={loading}
              >
                <option value="weekly">Weekly</option>
              </Select>
              <Button
                variant="primary"
                onClick={handleCompileInternal}
                disabled={loading}
              >
                {loading ? 'Kompilerar...' : 'Kompilera rapport'}
              </Button>
              {loading && (
                <span className="fortknox-inline-hint">
                  Lokal AI arbetar – kan ta upp till 3 min.
                </span>
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

            {error && !loading && (
              <div className="fortknox-error-card">
                <h4>Fel</h4>
                <p>{error.error_code}</p>
                {error.reasons && error.reasons.length > 0 && (
                  <ul>
                    {error.reasons.slice(0, 5).map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {report && !loading && (
              <div className="fortknox-report-container">
                <div className="fortknox-report-header">
                  <CheckCircle size={18} />
                  <span>Rapport genererad</span>
                </div>
                {renderMarkdown(report.rendered_markdown)}
                {report.input_fingerprint && (
                  <div className="fortknox-audit-footer">
                    <div>Fingerprint: {report.input_fingerprint.substring(0, 16)}...</div>
                    <div>Policy: {report.policy_id} v{report.policy_version}</div>
                    <div>Ruleset: {report.ruleset_hash}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'external' && (
          <div className="fortknox-station-external">
            <div className="fortknox-station-selection">
              <h3>Underlag</h3>
              {snapshotLoading ? (
                <div className="fortknox-loading">
                  <Loader className="spinner" />
                </div>
              ) : snapshot ? (
                <div className="fortknox-item-list">
                  {(snapshot.input_manifest || []).map((item) => {
                    const key = `${item.type}_${item.id}`
                    const isIncluded = selection.include.some(i => i.type === item.type && i.id === item.id)
                    const isBlocking = blockingItems.has(key)
                    const hasDatetimeMasked = item.datetime_masked === true
                    const isFixing = fixingItems.has(key)
                    const rowErr = rowErrors.get(key)
                    
                    return (
                      <div key={key} className={`fortknox-item-row ${isBlocking ? 'blocking' : ''}`}>
                        <input
                          type="checkbox"
                          checked={isIncluded}
                          onChange={() => toggleItemSelection(item)}
                        />
                        <div className="fortknox-item-info">
                          <span className="fortknox-item-type">{item.type === 'document' ? <FileText size={14} /> : <StickyNote size={14} />}</span>
                          <Badge variant="normal">
                            {item.origin === 'scout' ? 'AUTO' : 'MANUAL'}
                          </Badge>
                          <span className="fortknox-item-title">{item.title}</span>
                          <Badge variant={isBlocking ? 'sensitive' : 'normal'}>
                            {item.sanitize_level}
                          </Badge>
                          {hasDatetimeMasked && <Badge variant="normal">Datum maskat</Badge>}
                          {isBlocking && <Badge variant="sensitive">BLOCKERAR</Badge>}
                        </div>
                        <div className="fortknox-item-actions">
                          {isBlocking && !rowErr && (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => handleAutofixItem(item)}
                              disabled={isFixing}
                            >
                              {isFixing ? 'Fixing...' : 'Autofixa'}
                            </Button>
                          )}
                          {rowErr && rowErr.code === 'ORIGINAL_MISSING' && (
                            <>
                              <span className="row-inline-help">Original saknas. Välj “Exkludera”.</span>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => toggleItemSelection(item)}
                              >
                                Exkludera
                              </Button>
                            </>
                          )}
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => handleEditItem(item)}
                          >
                            <Edit size={14} />
                          </Button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div>Inget underlag hittat</div>
              )}
            </div>

            <div className="fortknox-station-result">
              <div className="fortknox-station-controls">
                <Select
                  value={templateId}
                  onChange={(e) => setTemplateId(e.target.value)}
                  disabled={loading}
                >
                  <option value="weekly">Weekly</option>
                </Select>
                {blockingItems.size > 0 && (
                  <Button
                    variant="secondary"
                    onClick={handleAutofixAll}
                    disabled={fixingItems.size > 0}
                  >
                    Autofixa blockerande ({blockingItems.size})
                  </Button>
                )}
                <Button
                  variant="primary"
                  onClick={handleCompileExternal}
                  disabled={loading}
                >
                  {loading ? 'Kompilerar...' : 'Kompilera Extern'}
                </Button>
                {loading && (
                  <span className="fortknox-inline-hint">
                    Lokal AI arbetar – kan ta upp till 3 min.
                  </span>
                )}
              </div>

              {error && !loading && status === 'BLOCKED' && (
                <div className="fortknox-fix-center">
                  <h4>Det här behöver åtgärdas för Extern policy</h4>
                  <ul>
                    {error.reasons?.slice(0, 5).map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {error && !loading && status === 'ERROR' && (
                <div className="fortknox-error-card">
                  <h4>
                    {error.error_code === 'EMPTY_INPUT_SET' 
                      ? 'Tomt underlag'
                      : 'Tekniskt fel'}
                  </h4>
                  <p>
                    {error.error_code === 'EMPTY_INPUT_SET'
                      ? 'Du har exkluderat allt underlag. Välj minst ett dokument eller en anteckning.'
                      : error.detail || 'Okänt fel'}
                  </p>
                </div>
              )}

              {loading && (
                <div className="fortknox-loading">
                  <div className="fortknox-skeleton shimmer"></div>
                  <div className="fortknox-skeleton shimmer"></div>
                </div>
              )}

              {report && !loading && (
                <div className="fortknox-report-container">
                  <div className="fortknox-report-header">
                    <CheckCircle size={18} />
                    <span>Rapport genererad</span>
                  </div>
                  <div className="fortknox-report-actions">
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
                  {renderMarkdown(report.rendered_markdown)}
                  {report.input_fingerprint && (
                    <div className="fortknox-audit-footer">
                      <div>Fingerprint: {report.input_fingerprint.substring(0, 16)}...</div>
                      <div>Policy: {report.policy_id} v{report.policy_version}</div>
                      <div>Ruleset: {report.ruleset_hash}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {showEditModal && editingItem && (
          <Modal
            isOpen={showEditModal}
            onClose={() => setShowEditModal(false)}
            title={`Redigera ${editingItem.type === 'document' ? 'dokument' : 'anteckning'}`}
            contentClassName="modal-wide"
          >
            <div className="fortknox-edit-modal">
              {saving && editText === '' ? (
                <div className="fortknox-loading">
                  <Loader className="spinner" />
                  <span>Laddar innehåll...</span>
                </div>
              ) : (
                <>
                  <div className="form-group">
                    <label>Sanitize Level</label>
                    <Select
                      value={editLevel}
                      onChange={(e) => setEditLevel(e.target.value)}
                    >
                      <option value="normal">Normal</option>
                      <option value="strict">Strict (rekommenderas för Extern)</option>
                      <option value="paranoid">Paranoid</option>
                    </Select>
                  </div>
                  <div className="form-group">
                    <label>Innehåll (maskat/sanerat)</label>
                    <textarea
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      rows={15}
                      placeholder="Redigera innehållet här..."
                    />
                  </div>
                  <div className="fortknox-edit-actions">
                    <Button onClick={() => {
                      setShowEditModal(false)
                      setEditingItem(null)
                      setEditText('')
                    }}>Avbryt</Button>
                    <Button variant="primary" onClick={handleSaveEdit} disabled={saving}>
                      {saving ? 'Sparar...' : 'Spara och kompilera'}
                    </Button>
                  </div>
                </>
              )}
            </div>
          </Modal>
        )}
      </div>
    </div>
  )
}

export default FortKnoxStation
