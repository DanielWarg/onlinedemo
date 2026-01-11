import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { apiUrl } from '../lib/api'
import { formatScoutDate } from '../lib/datetime'
import { formatScoutSource } from '../lib/scout'
import './Scout.css'

function Scout() {
  const location = useLocation()
  const [activeTab, setActiveTab] = useState('items')
  const [scoutItems, setScoutItems] = useState([])
  const [itemHours, setItemHours] = useState(24)
  const [sourceFilter, setSourceFilter] = useState('all')
  const [feeds, setFeeds] = useState([])
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [newFeedName, setNewFeedName] = useState('')
  const [newFeedUrl, setNewFeedUrl] = useState('')
  const [flash, setFlash] = useState(null) // { type: 'error'|'success', text: string }
  const [editingFeedId, setEditingFeedId] = useState(null)
  const [editFeedName, setEditFeedName] = useState('')
  const [editFeedUrl, setEditFeedUrl] = useState('')
  const [savingFeed, setSavingFeed] = useState(false)

  const username = 'admin'
  const password = 'password'
  const auth = btoa(`${username}:${password}`)

  useEffect(() => {
    const params = new URLSearchParams(location.search || '')
    const tab = params.get('tab')
    if (tab === 'feeds') setActiveTab('feeds')
    if (tab === 'items') setActiveTab('items')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search])

  useEffect(() => {
    setFlash(null)
    if (activeTab === 'items') {
      fetchItems()
    } else {
      fetchFeeds()
    }
  }, [activeTab, itemHours])

  const fetchItems = async () => {
    setLoading(true)
    try {
      const limit = itemHours > 168 ? 200 : 50
      const response = await fetch(apiUrl(`/scout/items?hours=${itemHours}&limit=${limit}`), {
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      if (!response.ok) throw new Error('Kunde inte hämta leads')
      const data = await response.json()
      setScoutItems(data)
    } catch (err) {
      console.error('Error fetching scout items:', err)
      setScoutItems([])
      setFlash({ type: 'error', text: 'Kunde inte hämta leads just nu.' })
    } finally {
      setLoading(false)
    }
  }

  const fetchFeeds = async () => {
    setLoading(true)
    try {
      const response = await fetch(apiUrl('/scout/feeds'), {
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      if (!response.ok) throw new Error('Kunde inte hämta källor')
      const data = await response.json()
      setFeeds(data)
    } catch (err) {
      console.error('Error fetching feeds:', err)
      setFeeds([])
      setFlash({ type: 'error', text: 'Kunde inte hämta källor just nu.' })
    } finally {
      setLoading(false)
    }
  }

  const handleFetch = async () => {
    setFetching(true)
    try {
      const response = await fetch(apiUrl('/scout/fetch'), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      if (!response.ok) throw new Error('Kunde inte uppdatera källor')
      // Refresh items after fetch
      await fetchItems()
    } catch (err) {
      console.error('Error fetching feeds:', err)
      setFlash({ type: 'error', text: 'Kunde inte uppdatera källor.' })
    } finally {
      setFetching(false)
    }
  }

  const handleAddFeed = async () => {
    if (!newFeedName || !newFeedUrl) {
      setFlash({ type: 'error', text: 'Fyll i både namn och URL.' })
      return
    }
    try {
      const response = await fetch(apiUrl('/scout/feeds'), {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: newFeedName,
          url: newFeedUrl
        })
      })
      if (!response.ok) throw new Error('Kunde inte skapa källa')
      setNewFeedName('')
      setNewFeedUrl('')
      await fetchFeeds()
      setFlash({ type: 'success', text: 'Källa tillagd.' })
    } catch (err) {
      console.error('Error creating feed:', err)
      setFlash({ type: 'error', text: 'Kunde inte skapa källa.' })
    }
  }

  const handleDisableFeed = async (feedId) => {
    try {
      const response = await fetch(apiUrl(`/scout/feeds/${feedId}`), {
        method: 'DELETE',
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      if (!response.ok) throw new Error('Kunde inte inaktivera källa')
      await fetchFeeds()
    } catch (err) {
      console.error('Error disabling feed:', err)
      setFlash({ type: 'error', text: 'Kunde inte inaktivera källa.' })
    }
  }

  const startEditFeed = (feed) => {
    setFlash(null)
    setEditingFeedId(feed.id)
    setEditFeedName(feed.name || '')
    setEditFeedUrl(feed.url || '')
  }

  const cancelEditFeed = () => {
    setEditingFeedId(null)
    setEditFeedName('')
    setEditFeedUrl('')
    setSavingFeed(false)
  }

  const handleUpdateFeed = async (feedId) => {
    if (!editFeedName || !editFeedUrl) {
      setFlash({ type: 'error', text: 'Fyll i både namn och URL.' })
      return
    }
    setSavingFeed(true)
    try {
      const response = await fetch(apiUrl(`/scout/feeds/${feedId}`), {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: editFeedName,
          url: editFeedUrl
        })
      })
      if (!response.ok) throw new Error('Kunde inte uppdatera källa')
      await fetchFeeds()
      setFlash({ type: 'success', text: 'Källa uppdaterad.' })
      cancelEditFeed()
    } catch (err) {
      console.error('Error updating feed:', err)
      setFlash({ type: 'error', text: 'Kunde inte uppdatera källa.' })
      setSavingFeed(false)
    }
  }

  const handleEnableFeed = async (feedId) => {
    try {
      const response = await fetch(apiUrl(`/scout/feeds/${feedId}`), {
        method: 'PUT',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ is_enabled: true })
      })
      if (!response.ok) throw new Error('Kunde inte aktivera källa')
      await fetchFeeds()
      setFlash({ type: 'success', text: 'Källa aktiverad.' })
    } catch (err) {
      console.error('Error enabling feed:', err)
      setFlash({ type: 'error', text: 'Kunde inte aktivera källa.' })
    }
  }

  return (
    <div className="scout-page">
      <Link to="/projects" className="back-link">← Tillbaka till kontrollrum</Link>
      <div className="scout-header">
        <h1 className="scout-title">Scout</h1>
      </div>

      {flash?.text && (
        <div className={`scout-flash ${flash.type === 'success' ? 'scout-flash-success' : 'scout-flash-error'}`}>
          {flash.text}
        </div>
      )}

      <div className="scout-tabs">
        <button
          className={`scout-tab ${activeTab === 'items' ? 'active' : ''}`}
          onClick={() => setActiveTab('items')}
        >
          Senaste 24h
        </button>
        <button
          className={`scout-tab ${activeTab === 'feeds' ? 'active' : ''}`}
          onClick={() => setActiveTab('feeds')}
        >
          Källor
        </button>
      </div>

      {activeTab === 'items' && (
        <div className="scout-content">
          <div className="scout-actions">
            <div className="scout-items-range">
              <span className="scout-items-range-label">Tidsintervall</span>
              <select
                className="scout-items-range-select"
                value={itemHours}
                onChange={(e) => setItemHours(parseInt(e.target.value, 10))}
              >
                <option value={24}>Senaste 24h</option>
                <option value={168}>Senaste 7 dagar</option>
                <option value={720}>Senaste 30 dagar</option>
                <option value={8760}>Senaste 12 månader</option>
              </select>
            </div>
            <div className="scout-items-range">
              <span className="scout-items-range-label">Källa</span>
              <select
                className="scout-items-range-select"
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
              >
                <option value="all">Alla</option>
                {Array.from(new Set(scoutItems.map(i => i.raw_source).filter(Boolean))).map((src) => (
                  <option key={src} value={src}>{src}</option>
                ))}
              </select>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="scout-fetch-btn"
              onClick={handleFetch}
              disabled={fetching}
            >
              {fetching ? 'Uppdaterar...' : 'Uppdatera nu'}
            </Button>
          </div>

          {loading ? (
            <p className="scout-loading">Laddar...</p>
          ) : scoutItems.length > 0 ? (
            <div className="scout-items-list-full">
              {scoutItems
                .filter(item => sourceFilter === 'all' || item.raw_source === sourceFilter)
                .map(item => (
                <div key={item.id} className="scout-item-full">
                  <Badge variant="normal" className="scout-item-badge">
                    {formatScoutSource(item.raw_source)}
                  </Badge>
                  <span className="scout-item-time-full">
                    {formatScoutDate(item.published_at || item.fetched_at)}
                  </span>
                  <a
                    href={item.link}
                    target="_blank"
                    rel="noopener"
                    className="scout-item-link"
                  >
                    {item.title}
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <p className="scout-empty-full">Inga leads</p>
          )}
        </div>
      )}

      {activeTab === 'feeds' && (
        <div className="scout-content">
          <div className="scout-feeds-form">
            <h3 className="scout-feeds-form-title">Lägg till källa</h3>
            <div className="scout-feeds-form-fields">
              <Input
                type="text"
                placeholder="Namn"
                value={newFeedName}
                onChange={(e) => setNewFeedName(e.target.value)}
                className="scout-feeds-input"
              />
              <Input
                type="text"
                placeholder="URL"
                value={newFeedUrl}
                onChange={(e) => setNewFeedUrl(e.target.value)}
                className="scout-feeds-input"
              />
              <Button
                variant="primary"
                size="sm"
                className="scout-feeds-add-btn"
                onClick={handleAddFeed}
              >
                Lägg till
              </Button>
            </div>
          </div>

          {loading ? (
            <p className="scout-loading">Laddar...</p>
          ) : feeds.length > 0 ? (
            <div className="scout-feeds-list">
              {feeds.map(feed => (
                <div key={feed.id} className={`scout-feed-item ${editingFeedId === feed.id ? 'editing' : ''}`}>
                  {editingFeedId === feed.id ? (
                    <>
                      <div className="scout-feed-edit-fields">
                        <Input
                          type="text"
                          value={editFeedName}
                          onChange={(e) => setEditFeedName(e.target.value)}
                          placeholder="Namn"
                        />
                        <Input
                          type="text"
                          value={editFeedUrl}
                          onChange={(e) => setEditFeedUrl(e.target.value)}
                          placeholder="URL"
                        />
                      </div>
                      <div className="scout-feed-actions">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleUpdateFeed(feed.id)}
                          disabled={savingFeed}
                        >
                          {savingFeed ? 'Sparar...' : 'Spara'}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={cancelEditFeed}
                          disabled={savingFeed}
                        >
                          Avbryt
                        </Button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="scout-feed-info">
                        <span className="scout-feed-name">{feed.name}</span>
                        <span className="scout-feed-url">{feed.url || '(ingen URL)'}</span>
                        {feed.is_enabled ? (
                          <Badge variant="normal" className="scout-feed-badge">Aktiverad</Badge>
                        ) : (
                          <Badge variant="normal" className="scout-feed-badge disabled">Inaktiverad</Badge>
                        )}
                      </div>
                      <div className="scout-feed-actions">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => startEditFeed(feed)}
                        >
                          Redigera
                        </Button>
                        {feed.is_enabled ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="scout-feed-disable-btn"
                            onClick={() => handleDisableFeed(feed.id)}
                          >
                            Inaktivera
                          </Button>
                        ) : (
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleEnableFeed(feed.id)}
                          >
                            Aktivera
                          </Button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="scout-empty-full">Inga feeds</p>
          )}
        </div>
      )}
    </div>
  )
}

export default Scout
