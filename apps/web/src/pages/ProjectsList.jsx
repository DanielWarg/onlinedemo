import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Modal } from '../ui/Modal'
import { Input } from '../ui/Input'
import CreateProject from './CreateProject'
import { getDueUrgency } from '../lib/urgency'
import { apiUrl } from '../lib/api'
import { formatScoutDate } from '../lib/datetime'
import { formatScoutSource } from '../lib/scout'
import { FolderPlus, Folder, Search, Calendar, Eye, Lock, FileText, ArrowRight, RefreshCw, Plus, Trash2, ExternalLink, Rss, X, Loader2 } from 'lucide-react'
import './ProjectsList.css'

function ProjectsList() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [hiddenScoutItems, setHiddenScoutItems] = useState(new Set())
  const [creatingFromScoutItem, setCreatingFromScoutItem] = useState(null)
  const [scoutItems, setScoutItems] = useState([])
  const [scoutFetching, setScoutFetching] = useState(false)
  const [showScoutModal, setShowScoutModal] = useState(false)
  const [scoutModalActiveTab, setScoutModalActiveTab] = useState('items')
  const [scoutModalItems, setScoutModalItems] = useState([])
  const [scoutModalFeeds, setScoutModalFeeds] = useState([])
  const [scoutModalLoading, setScoutModalLoading] = useState(false)
  const [scoutModalFetching, setScoutModalFetching] = useState(false)
  const [newFeedName, setNewFeedName] = useState('')
  const [newFeedUrl, setNewFeedUrl] = useState('')

  const fetchProjects = async () => {
    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)
      
      const response = await fetch(apiUrl('/projects'), {
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      
      if (!response.ok) throw new Error('Kunde inte hämta projekt')
      
      const data = await response.json()
      setProjects(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  useEffect(() => {
    const fetchScoutItems = async () => {
      try {
        const username = 'admin'
        const password = 'password'
        const auth = btoa(`${username}:${password}`)
        
        const response = await fetch(apiUrl('/scout/items?hours=168&limit=50'), {
          headers: {
            'Authorization': `Basic ${auth}`
          },
          credentials: 'omit'
        })
        
        if (!response.ok) throw new Error('Kunde inte hämta Scout-item')
        
        const data = await response.json()
        setScoutItems(data)
      } catch (err) {
        console.error('Error fetching scout items:', err)
        setScoutItems([])
      }
    }
    
    // Fetch immediately
    fetchScoutItems()
    
    // Auto-update items every 5 minutes
    const itemsInterval = setInterval(fetchScoutItems, 5 * 60 * 1000)
    
    // Auto-fetch feeds every 30 minutes
    const fetchFeeds = async () => {
      try {
        const username = 'admin'
        const password = 'password'
        const auth = btoa(`${username}:${password}`)
        
        await fetch(apiUrl('/scout/fetch'), {
          method: 'POST',
          headers: {
            'Authorization': `Basic ${auth}`
          }
        })
        // Refresh items after fetching feeds
        fetchScoutItems()
      } catch (err) {
        console.error('Error auto-fetching feeds:', err)
      }
    }
    
    // Fetch feeds every 30 minutes
    const feedsInterval = setInterval(fetchFeeds, 30 * 60 * 1000)
    
    return () => {
      clearInterval(itemsInterval)
      clearInterval(feedsInterval)
    }
  }, [])

  // Scout box fetch function
  const handleScoutBoxFetch = async () => {
    setScoutFetching(true)
    try {
      const username = 'admin'
      const password = 'password'
      const auth = btoa(`${username}:${password}`)
      
    await fetch(apiUrl('/scout/fetch'), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      
      // Refresh items after fetching feeds
      const response = await fetch(apiUrl('/scout/items?hours=168&limit=50'), {
        headers: {
          'Authorization': `Basic ${auth}`
        },
        credentials: 'omit'
      })
      
      if (response.ok) {
        const data = await response.json()
        setScoutItems(data)
      }
    } catch (err) {
      console.error('Error fetching scout feeds:', err)
    } finally {
      setScoutFetching(false)
    }
  }

  // Scout modal functions
  const scoutAuth = btoa('admin:password')

  const fetchScoutModalItems = useCallback(async () => {
    setScoutModalLoading(true)
    try {
      const response = await fetch(apiUrl('/scout/items?hours=168&limit=50'), {
        headers: {
          'Authorization': `Basic ${scoutAuth}`
        }
      })
      if (!response.ok) throw new Error('Kunde inte hämta items')
      const data = await response.json()
      setScoutModalItems(data)
    } catch (err) {
      console.error('Error fetching scout items:', err)
      setScoutModalItems([])
    } finally {
      setScoutModalLoading(false)
    }
  }, [scoutAuth])

  const fetchScoutModalFeeds = async () => {
    setScoutModalLoading(true)
    try {
      const response = await fetch(apiUrl('/scout/feeds'), {
        headers: {
          'Authorization': `Basic ${scoutAuth}`
        }
      })
      if (!response.ok) throw new Error('Kunde inte hämta feeds')
      const data = await response.json()
      setScoutModalFeeds(data)
    } catch (err) {
      console.error('Error fetching feeds:', err)
      setScoutModalFeeds([])
    } finally {
      setScoutModalLoading(false)
    }
  }

  useEffect(() => {
    if (showScoutModal) {
      if (scoutModalActiveTab === 'items') {
        fetchScoutModalItems()
        
        // Auto-update items every 2 minutes when modal is open
        const itemsInterval = setInterval(fetchScoutModalItems, 2 * 60 * 1000)
        return () => clearInterval(itemsInterval)
      } else {
        fetchScoutModalFeeds()
      }
    }
  }, [showScoutModal, scoutModalActiveTab, fetchScoutModalItems])

  const handleScoutModalFetch = async () => {
    setScoutModalFetching(true)
    try {
      const response = await fetch(apiUrl('/scout/fetch'), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${scoutAuth}`
        }
      })
      if (!response.ok) throw new Error('Kunde inte hämta feeds')
      await fetchScoutModalItems()
    } catch (err) {
      console.error('Error fetching feeds:', err)
      alert('Kunde inte uppdatera feeds')
    } finally {
      setScoutModalFetching(false)
    }
  }

  const handleScoutModalAddFeed = async () => {
    if (!newFeedName || !newFeedUrl) {
      alert('Fyll i både namn och URL')
      return
    }
    try {
      const response = await fetch(apiUrl('/scout/feeds'), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${scoutAuth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: newFeedName,
          url: newFeedUrl
        })
      })
      if (!response.ok) throw new Error('Kunde inte skapa feed')
      setNewFeedName('')
      setNewFeedUrl('')
      await fetchScoutModalFeeds()
    } catch (err) {
      console.error('Error creating feed:', err)
      alert('Kunde inte skapa feed')
    }
  }

  const handleScoutModalDisableFeed = async (feedId) => {
    try {
      const response = await fetch(apiUrl(`/scout/feeds/${feedId}`), {
        method: 'DELETE',
        headers: {
          'Authorization': `Basic ${scoutAuth}`
        }
      })
      if (!response.ok) throw new Error('Kunde inte inaktivera feed')
      await fetchScoutModalFeeds()
    } catch (err) {
      console.error('Error disabling feed:', err)
      alert('Kunde inte inaktivera feed')
    }
  }

  const handleCreateSuccess = (project) => {
    setShowCreateModal(false)
    fetchProjects()
    navigate(`/projects/${project.id}`)
  }

  const handleCreateProjectFromFeed = async (feedUrl, feedName, mode = 'fulltext') => {
    try {
      const auth = btoa('admin:password')
      const response = await fetch(apiUrl('/projects/from-feed'), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          url: feedUrl,
          project_name: feedName,
          limit: 10,
          mode: mode
        })
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Kunde inte skapa projekt från feed')
      }
      
      const data = await response.json()
      setShowScoutModal(false)
      navigate(`/projects/${data.project_id}`)
    } catch (err) {
      alert(`Fel: ${err.message}`)
    }
  }

  const handleCreateProjectFromScoutItem = async (itemId) => {
    setCreatingFromScoutItem(itemId)
    try {
      const auth = btoa('admin:password')
      const response = await fetch(apiUrl('/projects/from-scout-item'), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ scout_item_id: itemId })
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Kunde inte skapa projekt från scout-item')
      }
      
      const data = await response.json()
      navigate(`/projects/${data.project_id}`)
    } catch (err) {
      alert(`Fel: ${err.message}`)
    } finally {
      setCreatingFromScoutItem(null)
    }
  }

  const handleHideScoutItem = (itemId) => {
    setHiddenScoutItems(prev => new Set([...prev, itemId]))
  }

  if (loading) return <div className="projects-list-page">Laddar...</div>
  if (error) return <div className="projects-list-page">Fel: {error}</div>

  const getClassificationLabel = (classification) => {
    if (classification === 'source-sensitive') {
      return 'Källkritisk'
    }
    if (classification === 'sensitive') {
      return 'Känslig'
    }
    return 'Offentlig'
  }

  const getClassificationClass = (classification) => {
    if (classification === 'sensitive' || classification === 'source-sensitive') {
      return 'badge-sensitive'
    }
    return 'badge-normal'
  }

  // Get projects with due dates for Due Dates widget
  // Prioritize urgent deadlines (warning/danger), then sort by date
  const projectsWithDueDates = projects
    .filter(p => p.due_date)
    .map(p => ({
      ...p,
      urgency: getDueUrgency(p.due_date)
    }))
    .sort((a, b) => {
      // First: prioritize urgent (warning/danger) over normal
      const aUrgent = a.urgency.variant === 'warning' || a.urgency.variant === 'danger'
      const bUrgent = b.urgency.variant === 'warning' || b.urgency.variant === 'danger'
      if (aUrgent && !bUrgent) return -1
      if (!aUrgent && bUrgent) return 1
      // Then: sort by date (earliest first)
      if (!a.urgency.normalizedDate) return 1
      if (!b.urgency.normalizedDate) return -1
      return a.urgency.normalizedDate.localeCompare(b.urgency.normalizedDate)
    })
    .slice(0, 4) // Limit to 4 most important

  // Filter projects by search query
  const filteredProjects = projects
    .filter(project => 
      project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (project.description && project.description.toLowerCase().includes(searchQuery.toLowerCase()))
    )
    .sort((a, b) => {
      // Sort by due_date: projects with due_date first, then by date (earliest first)
      if (!a.due_date && !b.due_date) return 0
      if (!a.due_date) return 1 // a without due_date goes last
      if (!b.due_date) return -1 // b without due_date goes last
      
      // Both have due_date, sort by date (earliest first)
      const dateA = new Date(a.due_date).getTime()
      const dateB = new Date(b.due_date).getTime()
      return dateA - dateB
    })

  // Get last updated project
  const lastUpdatedProject = projects.length > 0 
    ? projects.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))[0]
    : null

  return (
    <div className="projects-list-page">
      <div className="projects-header">
        <h2 className="projects-title">Kontrollrum</h2>
      </div>

      {/* Scout - Full Width */}
      <Card className="overview-card overview-card-fullwidth scout-card-fullwidth">
        <div className="overview-card-header">
          <h3 className="overview-card-title">Scout – senaste 7 dagar</h3>
        </div>
        <div className="overview-card-content">
            {scoutItems.filter(item => !hiddenScoutItems.has(item.id)).length > 0 ? (
              <div className="scout-widget-list">
                {scoutItems.filter(item => !hiddenScoutItems.has(item.id)).map(item => (
                <div key={item.id} className="scout-widget-item">
                  <a
                    href={item.link || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="scout-widget-item-link"
                    onClick={(e) => {
                      if (!item.link) {
                        e.preventDefault()
                      }
                    }}
                  >
                    <Badge variant="normal" className="scout-widget-badge">{formatScoutSource(item.raw_source)}</Badge>
                    <span className="scout-widget-title">{item.title}</span>
                    <span className="scout-widget-time">
                      {formatScoutDate(item.published_at || item.fetched_at)}
                    </span>
                  </a>
                  <div className="scout-widget-item-actions">
                    <button
                      className="scout-widget-item-create-btn"
                      onClick={() => handleCreateProjectFromScoutItem(item.id)}
                      disabled={creatingFromScoutItem === item.id}
                      title="Skapa projekt från lead"
                    >
                      {creatingFromScoutItem === item.id ? (
                        <Loader2 size={14} className="spinning" />
                      ) : (
                        <span>Skapa projekt</span>
                      )}
                    </button>
                    <button
                      className="scout-widget-item-hide-btn"
                      onClick={() => handleHideScoutItem(item.id)}
                      title="Dölj lead"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="overview-empty-state">
              <p className="overview-empty-text">Inga leads</p>
            </div>
          )}
          <div className="scout-box-actions">
            <Button
              variant="outline"
              size="sm"
              className="btn-scout-refresh"
              onClick={handleScoutBoxFetch}
              disabled={scoutFetching}
              title="Uppdatera källor"
            >
              <RefreshCw size={14} className={scoutFetching ? 'spinning' : ''} />
              <span>{scoutFetching ? 'Uppdaterar...' : 'Uppdatera'}</span>
            </Button>
            <Link to="/scout?tab=feeds" className="btn btn-outline btn-sm btn-overview">
              <span>Redigera</span>
            </Link>
            <Link to="/scout" className="btn btn-outline btn-sm btn-overview">
              <Eye size={16} />
              <span>Visa alla</span>
            </Link>
          </div>
        </div>
      </Card>

      {/* Dina Projekt - Full Width */}
      <Card className="overview-card overview-card-fullwidth projects-card-fullwidth">
        <div className="overview-card-header">
          <h3 className="overview-card-title">Dina Projekt</h3>
        </div>
        <div className="overview-card-content">
          {filteredProjects.length === 0 ? (
            <div className="overview-empty-state">
              <p className="overview-empty-text">
                {searchQuery ? 'Inga matchningar' : 'Inga projekt'}
              </p>
            </div>
          ) : (
            <div className="projects-list-compact">
              {filteredProjects.map(project => {
                const statusLabels = {
                  'research': 'Research',
                  'processing': 'Bearbetning',
                  'fact_check': 'Faktakoll',
                  'ready': 'Klar',
                  'archived': 'Arkiverad'
                }
                const urgency = getDueUrgency(project.due_date)
                
                return (
                  <Link 
                    key={project.id} 
                    to={`/projects/${project.id}`} 
                    className="project-item-compact"
                  >
                    <div className="project-item-compact-content">
                      <div className="project-item-main">
                        <Folder size={14} className="project-item-icon" />
                        <span className="project-item-name">{project.name}</span>
                      </div>
                      <div className="project-item-meta">
                        <span className="project-status-badge">
                          {statusLabels[project.status] || 'Research'}
                        </span>
                        {project.due_date && (
                          <span className={`project-due-date-badge ${urgency.variant}`}>
                            {urgency.normalizedDate}
                            {urgency.label && ` • ${urgency.label}`}
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>
                )
              })}
            </div>
          )}
          <Link to="/projects" className="btn btn-outline btn-sm btn-overview">
            <Eye size={16} />
            <span>Visa alla</span>
          </Link>
        </div>
      </Card>

      {/* Overview Grid - Other Widgets */}
      <div className="overview-grid">
        {/* Projekt Widget */}
        <Card className="overview-card">
          <div className="overview-card-header">
            <h3 className="overview-card-title">Projekt</h3>
          </div>
          <div className="overview-card-content">
            <div className="project-widget-search">
              <Search size={16} className="search-icon" />
              <Input
                type="text"
                placeholder="Sök projekt..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="project-search-input"
              />
            </div>
            <Button
              variant="primary"
              size="sm"
              className="btn-create-project-inline"
              onClick={() => setShowCreateModal(true)}
            >
              <FolderPlus size={16} />
              <span>Nytt projekt</span>
            </Button>
            {lastUpdatedProject && (
              <div className="project-widget-meta">
                <span className="project-widget-meta-label">Senast uppdaterade:</span>
                <span className="project-widget-meta-value">{lastUpdatedProject.name}</span>
              </div>
            )}
            <div className="project-widget-count">
              <span className="project-widget-count-label">Totalt:</span>
              <span className="project-widget-count-value">{projects.length} projekt</span>
            </div>
          </div>
        </Card>

        {/* Due Dates Widget */}
        <Card className="overview-card">
          <div className="overview-card-header">
            <h3 className="overview-card-title">Deadlines</h3>
          </div>
          <div className="overview-card-content">
            {projectsWithDueDates.length === 0 ? (
              <div className="overview-empty-state">
                <p className="overview-empty-text">Inga deadlines ännu</p>
              </div>
            ) : (
              <div className="due-dates-list">
                {projectsWithDueDates.map(project => (
                  <Link
                    key={project.id}
                    to={`/projects/${project.id}`}
                    className="due-date-item"
                  >
                    <div className="due-date-item-content">
                      <span className="due-date-item-name">{project.name}</span>
                      <div className="due-date-item-meta">
                        <span className="due-date-item-date">{project.urgency.normalizedDate}</span>
                        {project.urgency.label && (
                          <Badge 
                            variant="normal" 
                            className={`deadline-badge ${project.urgency.variant}`}
                          >
                            {project.urgency.label}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Fort Knox Widget */}
        <Card className="overview-card">
          <div className="overview-card-header">
            <h3 className="overview-card-title">Fort Knox</h3>
            <Badge variant="normal" className="fortknox-status-badge">REDO</Badge>
          </div>
          <div className="overview-card-content">
            <p className="overview-placeholder-text">
              Säkerhetshantering och åtkomstkontroll. Kompilera integritetsrapporter direkt från projektvyn.
            </p>
            {projects.length > 0 ? (
              <Link to="/fortknox" className="btn btn-outline btn-sm btn-overview">
                <Lock size={16} />
                <span>Öppna Fort Knox</span>
              </Link>
            ) : (
            <button className="btn btn-outline btn-sm" disabled>
              <Lock size={16} />
                <span>Skapa projekt först</span>
            </button>
            )}
          </div>
        </Card>

      </div>

      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Skapa nytt projekt"
      >
        <CreateProject
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleCreateSuccess}
        />
      </Modal>

      <Modal
        isOpen={showScoutModal}
        onClose={() => setShowScoutModal(false)}
        title="Scout – Senaste 7 dagar"
      >
        <div className="scout-modal-content">
          <div className="scout-modal-tabs">
            <button
              className={`scout-modal-tab ${scoutModalActiveTab === 'items' ? 'active' : ''}`}
              onClick={() => setScoutModalActiveTab('items')}
            >
              Senaste 7 dagar
            </button>
            <button
              className={`scout-modal-tab ${scoutModalActiveTab === 'feeds' ? 'active' : ''}`}
              onClick={() => setScoutModalActiveTab('feeds')}
            >
              Källor
            </button>
          </div>

          {scoutModalActiveTab === 'items' && (
            <div className="scout-modal-tab-content">
              <div className="scout-modal-actions">
                <button
                  className="scout-modal-fetch-btn"
                  onClick={handleScoutModalFetch}
                  disabled={scoutModalFetching}
                >
                  <RefreshCw size={14} />
                  <span>{scoutModalFetching ? 'Uppdaterar...' : 'Uppdatera nu'}</span>
                </button>
              </div>

              {scoutModalLoading ? (
                <p className="scout-modal-loading">Laddar...</p>
              ) : scoutModalItems.filter(item => !hiddenScoutItems.has(item.id)).length > 0 ? (
                <div className="scout-modal-items-list">
                  {scoutModalItems.filter(item => !hiddenScoutItems.has(item.id)).map(item => (
                    <div key={item.id} className="scout-modal-item">
                      <div className="scout-modal-item-header">
                        <Badge variant="normal">{formatScoutSource(item.raw_source)}</Badge>
                        <span className="scout-modal-item-time">
                          {formatScoutDate(item.published_at || item.fetched_at)}
                        </span>
                      </div>
                      <div className="scout-modal-item-content">
                        <a
                          href={item.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="scout-modal-item-link"
                        >
                          <span className="scout-modal-item-title">{item.title}</span>
                          <ExternalLink size={14} />
                        </a>
                        <div className="scout-modal-item-actions">
                          <button
                            className="scout-modal-item-create-btn"
                            onClick={() => handleCreateProjectFromScoutItem(item.id)}
                            disabled={creatingFromScoutItem === item.id}
                            title="Skapa projekt från lead"
                          >
                            {creatingFromScoutItem === item.id ? (
                              <Loader2 size={14} className="spinning" />
                            ) : (
                              <FolderPlus size={14} />
                            )}
                            <span>Skapa projekt</span>
                          </button>
                          <button
                            className="scout-modal-item-hide-btn"
                            onClick={() => handleHideScoutItem(item.id)}
                            title="Dölj lead"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="scout-modal-empty">Inga leads hittades för de senaste 7 dagarna.</p>
              )}
            </div>
          )}

          {scoutModalActiveTab === 'feeds' && (
            <div className="scout-modal-tab-content">
              <div className="scout-modal-feeds-form">
                <h3 className="scout-modal-feeds-form-title">Lägg till källa</h3>
                <div className="scout-modal-feeds-form-fields">
                  <input
                    type="text"
                    placeholder="Namn på källa (t.ex. Polisen Göteborg)"
                    value={newFeedName}
                    onChange={(e) => setNewFeedName(e.target.value)}
                    className="scout-modal-feeds-input"
                  />
                  <input
                    type="url"
                    placeholder="RSS-URL (t.ex. https://polisen.se/rss)"
                    value={newFeedUrl}
                    onChange={(e) => setNewFeedUrl(e.target.value)}
                    className="scout-modal-feeds-input"
                  />
                  <button
                    className="scout-modal-feeds-add-btn"
                    onClick={handleScoutModalAddFeed}
                  >
                    <Plus size={14} />
                    <span>Lägg till källa</span>
                  </button>
                </div>
              </div>

              {scoutModalLoading ? (
                <p className="scout-modal-loading">Laddar...</p>
              ) : scoutModalFeeds.length > 0 ? (
                <div className="scout-modal-feeds-list">
                  {scoutModalFeeds.map(feed => (
                    <div key={feed.id} className={`scout-modal-feed-item ${!feed.is_enabled ? 'disabled' : ''}`}>
                      <div className="scout-modal-feed-info">
                        <span className="scout-modal-feed-name">{feed.name}</span>
                        <span className="scout-modal-feed-url">{feed.url || 'Ingen URL angiven'}</span>
                      </div>
                      <div className="scout-modal-feed-actions">
                        {!feed.is_enabled && <Badge variant="danger">Inaktiverad</Badge>}
                        {feed.url && (
                          <button
                            className="scout-modal-feed-create-project-btn"
                            onClick={() => handleCreateProjectFromFeed(feed.url, feed.name)}
                            title="Skapa projekt från källa"
                          >
                            <Rss size={16} />
                            <span>Skapa projekt</span>
                          </button>
                        )}
                        <button
                          className="scout-modal-feed-disable-btn"
                          onClick={() => handleScoutModalDisableFeed(feed.id)}
                          title="Inaktivera källa"
                          disabled={!feed.is_enabled}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="scout-modal-empty">Inga källor tillagda.</p>
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}

export default ProjectsList

