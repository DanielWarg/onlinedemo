import React, { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { ArrowLeft, Info, Edit } from 'lucide-react'
import { apiUrl } from '../lib/api'
import './DocumentView.css'

function DocumentView() {
  const { projectId, documentId } = useParams()
  const [document, setDocument] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editText, setEditText] = useState('')
  const [saving, setSaving] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)

  useEffect(() => {
    const fetchDocument = async () => {
      try {
        const username = 'admin'
        const password = 'password'
        const auth = btoa(`${username}:${password}`)

        const response = await fetch(apiUrl(`/documents/${documentId}`), {
          headers: { 'Authorization': `Basic ${auth}` }
        })

        if (!response.ok) throw new Error('Failed to fetch document')

        const data = await response.json()
        setDocument(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchDocument()
  }, [documentId])

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
    if (classification === 'sensitive' || classification === 'source-sensitive') {
      return 'sensitive'
    }
    return 'normal'
  }

  const handleEdit = () => {
    setEditText(document.masked_text)
    setShowEditModal(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)
      
      const response = await fetch(apiUrl(`/documents/${documentId}`), {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          masked_text: editText
        })
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to update document')
      }
      
      const updatedDoc = await response.json()
      setDocument(updatedDoc)
      setShowEditModal(false)
    } catch (err) {
      console.error('Error updating document:', err)
      alert(`Kunde inte uppdatera dokument: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="document-page">Laddar...</div>
  if (error) return <div className="document-page">Fel: {error}</div>
  if (!document) return <div className="document-page">Dokument hittades inte</div>

  return (
    <div className="document-page">
      <div className="document-content">
        <div className="document-header-sticky">
          <Link to={`/projects/${projectId}`} className="document-back-link">
            <ArrowLeft size={16} />
            <span>Tillbaka till kontrollrum</span>
          </Link>
          <div className="document-header-info">
            <div className="document-title-row">
              <h1 className="document-title">{document.filename}</h1>
              <div className="document-title-actions">
                <button 
                  className="document-edit-btn"
                  onClick={handleEdit}
                  title="Redigera dokument"
                >
                  <Edit size={16} />
                </button>
                <Badge variant={getClassificationVariant(document.classification)}>
                  {getClassificationLabel(document.classification)}
                </Badge>
              </div>
            </div>
            <div className="document-meta">
              <div className="document-meta-masked">
                <span className="document-meta-label">Maskad vy</span>
                <div className="document-meta-tooltip-container">
                  <Info size={14} className="document-meta-info-icon" />
                  <div className="document-meta-tooltip">
                    Originalmaterial bevaras i säkert lager och exponeras aldrig i arbetsytan. All känslig information är automatiskt maskerad.
                  </div>
                </div>
              </div>
              <span className="document-meta-separator">•</span>
              <span className="document-meta-date">
                {new Date(document.created_at).toLocaleDateString('sv-SE')}
              </span>
            </div>
          </div>
        </div>
        <div className="document-text">
          {document.masked_text.split('\n').map((line, index) => {
            // Show enhancement notice after "Sammanfattning" or "Nyckelpunkter" headings
            const isSummaryHeading = line.trim() === '## Sammanfattning'
            const isKeyPointsHeading = line.trim() === '## Nyckelpunkter'
            const isFullTranscriptHeading = line.trim() === '## Fullständigt transkript'
            
            return (
              <React.Fragment key={index}>
                <p className="document-line">
                  {line || '\u00A0'}
                </p>
                {isSummaryHeading && (
                  <p className="document-enhancement-notice">
                    Sammanfattning och nyckelpunkter är språkligt förtydligade. Originaltranskript bevaras.
                  </p>
                )}
              </React.Fragment>
            )
          })}
        </div>
      </div>

      {/* Edit Document Modal */}
      <Modal isOpen={showEditModal} onClose={() => setShowEditModal(false)} title="Redigera dokument">
        <div className="edit-document-form">
          <div className="form-group">
            <label htmlFor="edit-document-text">Innehåll *</label>
            <textarea
              id="edit-document-text"
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              required
              rows={20}
              placeholder="Dokumentets innehåll..."
              style={{ 
                fontFamily: 'monospace', 
                fontSize: '0.9em',
                width: '100%',
                padding: 'var(--spacing-sm)',
                border: '1px solid var(--color-border-default)',
                borderRadius: 'var(--radius-sm)',
                resize: 'vertical'
              }}
            />
            <p className="form-help-text" style={{ fontSize: '0.875em', color: 'var(--color-text-muted)', marginTop: 'var(--spacing-xs)' }}>
              Texten kommer att gå genom samma sanitization-pipeline som vid uppladdning.
            </p>
          </div>
          
          <div className="modal-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setShowEditModal(false)
                setEditText('')
              }}
              disabled={saving}
            >
              Avbryt
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? 'Sparar...' : 'Spara ändringar'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default DocumentView
