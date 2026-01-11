import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { ExternalLink, Loader2 } from 'lucide-react'
import { apiUrl } from '../lib/api'
import './CreateProjectFromFeed.css'

function CreateProjectFromFeed({ onClose, initialFeedUrl = '', initialProjectName = '' }) {
  const navigate = useNavigate()
  
  const [feedUrl, setFeedUrl] = useState(initialFeedUrl)
  const [projectName, setProjectName] = useState(initialProjectName)
  const [limit, setLimit] = useState(10)
  const [previewData, setPreviewData] = useState(null)
  const [previewing, setPreviewing] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)
  const [previewError, setPreviewError] = useState(null)

  // Auto-preview if initialFeedUrl is provided
  useEffect(() => {
    if (initialFeedUrl && !previewData && !previewing && feedUrl === initialFeedUrl) {
      const autoPreview = async () => {
        setPreviewError(null)
        setPreviewData(null)
        setPreviewing(true)
        try {
          const response = await fetch(
            apiUrl(`/feeds/preview?url=${encodeURIComponent(initialFeedUrl.trim())}`),
            {
              headers: {
                'Authorization': `Basic ${auth}`
              }
            }
          )
          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}))
            throw new Error(errorData.detail || 'Kunde inte förhandsgranska feed')
          }
          const data = await response.json()
          setPreviewData(data)
          if (!projectName.trim() && data.title) {
            setProjectName(data.title)
          }
        } catch (err) {
          setPreviewError(err.message)
        } finally {
          setPreviewing(false)
        }
      }
      autoPreview()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialFeedUrl, feedUrl])

  const username = 'admin'
  const password = 'password'
  const auth = btoa(`${username}:${password}`)

  const handlePreview = async (e) => {
    e.preventDefault()
    setPreviewError(null)
    setPreviewData(null)
    
    if (!feedUrl.trim()) {
      setPreviewError('Ange en feed URL')
      return
    }

    setPreviewing(true)
    try {
      const response = await fetch(
        apiUrl(`/feeds/preview?url=${encodeURIComponent(feedUrl.trim())}`),
        {
          headers: {
            'Authorization': `Basic ${auth}`
          }
        }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Kunde inte förhandsgranska feed')
      }

      const data = await response.json()
      setPreviewData(data)
      
      // Autofyll projektnamn om det är tomt
      if (!projectName.trim() && data.title) {
        setProjectName(data.title)
      }
    } catch (err) {
      setPreviewError(err.message)
    } finally {
      setPreviewing(false)
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setError(null)

    if (!feedUrl.trim()) {
      setError('Ange en feed URL')
      return
    }

    setCreating(true)
    try {
      const response = await fetch(apiUrl('/projects/from-feed'), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          url: feedUrl.trim(),
          project_name: projectName.trim() || null,
          limit: limit
        })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Kunde inte skapa projekt från feed')
      }

      const result = await response.json()
      
      // Navigera till projektet
      navigate(`/projects/${result.project_id}`)
      
      // Stäng modal
      if (onClose) {
        onClose()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Inget datum'
    try {
      const date = new Date(dateStr)
      return date.toLocaleString('sv-SE', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return dateStr
    }
  }

  return (
    <form onSubmit={handleCreate} className="create-project-from-feed-form">
      {error && (
        <div className="form-error">
          {error}
        </div>
      )}

      <div className="form-group">
        <label htmlFor="feedUrl">Feed URL *</label>
        <Input
          id="feedUrl"
          type="url"
          value={feedUrl}
          onChange={(e) => setFeedUrl(e.target.value)}
          placeholder="https://example.com/feed.xml"
          required
          autoFocus
        />
        <p className="form-hint">
          RSS eller Atom feed URL. Endast http:// och https:// tillåtna.
        </p>
      </div>

      <div className="form-group">
        <label htmlFor="projectName">Projektnamn (valfritt)</label>
        <Input
          id="projectName"
          type="text"
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          placeholder="Autofylls från feed-titel efter förhandsgranskning"
        />
      </div>

      <div className="form-group">
        <label htmlFor="limit">Antal items att importera</label>
        <Select
          id="limit"
          value={limit}
          onChange={(e) => setLimit(parseInt(e.target.value))}
        >
          <option value="10">Senaste 10</option>
          <option value="25">Senaste 25</option>
        </Select>
      </div>

      <div className="form-actions">
        <Button
          type="button"
          variant="secondary"
          onClick={handlePreview}
          disabled={!feedUrl.trim() || previewing || creating}
        >
          {previewing ? (
            <>
              <Loader2 size={16} className="spinning" />
              <span>Förhandsgranskar...</span>
            </>
          ) : (
            <span>Förhandsgranska</span>
          )}
        </Button>
      </div>

      {previewError && (
        <div className="form-error">
          {previewError}
        </div>
      )}

      {previewData && (
        <div className="preview-section">
          <h3 className="preview-title">Förhandsgranskning</h3>
          <div className="preview-feed-info">
            <p><strong>Titel:</strong> {previewData.title}</p>
            {previewData.description && (
              <p><strong>Beskrivning:</strong> {previewData.description}</p>
            )}
            <p><strong>Antal items:</strong> {previewData.items.length}</p>
          </div>
          
          <div className="preview-items">
            <h4>Första 3 items:</h4>
            {previewData.items.slice(0, 3).map((item, index) => (
              <div key={index} className="preview-item">
                <div className="preview-item-header">
                  <h5 className="preview-item-title">{item.title || 'Ingen titel'}</h5>
                  {item.link && (
                    <a
                      href={item.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="preview-item-link"
                    >
                      <ExternalLink size={14} />
                    </a>
                  )}
                </div>
                {item.published && (
                  <p className="preview-item-date">{formatDate(item.published)}</p>
                )}
                {item.summary_text && (
                  <p className="preview-item-summary">
                    {item.summary_text.length > 200
                      ? `${item.summary_text.substring(0, 200)}...`
                      : item.summary_text}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="form-actions form-actions-bottom">
        <Button
          type="button"
          variant="secondary"
          onClick={onClose}
          disabled={creating}
        >
          Avbryt
        </Button>
        <Button
          type="submit"
          variant="success"
          disabled={!feedUrl.trim() || creating || previewing}
        >
          {creating ? (
            <>
              <Loader2 size={16} className="spinning" />
              <span>Skapar projekt...</span>
            </>
          ) : (
            <span>Skapa projekt</span>
          )}
        </Button>
      </div>
    </form>
  )
}

export default CreateProjectFromFeed
