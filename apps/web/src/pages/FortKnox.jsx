import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Lock, ArrowLeft } from 'lucide-react'
import { Select } from '../ui/Select'
import FortKnoxStation from '../components/FortKnoxStation'
import { apiUrl } from '../lib/api'
import './FortKnox.css'

function FortKnox() {
  const [projects, setProjects] = useState([])
  const [selectedProjectId, setSelectedProjectId] = useState(null)
  const [loading, setLoading] = useState(true)

  const username = 'admin'
  const password = 'password'
  const auth = btoa(`${username}:${password}`)

  useEffect(() => {
    fetchProjects()
  }, [])

  const fetchProjects = async () => {
    try {
      const response = await fetch(apiUrl('/projects'), {
        headers: {
          'Authorization': `Basic ${auth}`
        }
      })
      
      if (!response.ok) throw new Error('Failed to fetch projects')
      
      const data = await response.json()
      setProjects(data)
      
      // Auto-select first project if available
      if (data.length > 0 && !selectedProjectId) {
        setSelectedProjectId(data[0].id.toString())
      }
    } catch (err) {
      console.error('Error fetching projects:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fortknox-page">
      <div className="fortknox-page-header">
        <Link to="/projects" className="fortknox-back-link">
          <ArrowLeft size={16} />
          <span>Tillbaka till kontrollrum</span>
        </Link>
        <div className="fortknox-page-title-section">
          <div className="fortknox-page-title-left">
            <Lock size={24} className="fortknox-page-icon" />
            <div>
              <h1 className="fortknox-page-title">Fort Knox</h1>
              <p className="fortknox-page-subtitle">Isolerad sammanställning med strikt integritet</p>
            </div>
          </div>
        </div>
      </div>

      <div className="fortknox-page-content">
        <div className="fortknox-project-selector-section">
          <label htmlFor="project-select" className="fortknox-project-label">
            Välj projekt
          </label>
          {loading ? (
            <div className="fortknox-loading-projects">Laddar projekt...</div>
          ) : projects.length === 0 ? (
            <div className="fortknox-no-projects">
              <p>Inga projekt hittades.</p>
              <Link to="/projects" className="fortknox-create-link">
                Skapa nytt projekt
              </Link>
            </div>
          ) : (
            <Select
              id="project-select"
              value={selectedProjectId || ''}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="fortknox-project-select"
            >
              <option value="">-- Välj projekt --</option>
              {projects.map(project => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </Select>
          )}
        </div>

        {selectedProjectId && (
          <div className="fortknox-panel-container">
            <div className="fortknox-station-embedded">
              <FortKnoxStation projectId={selectedProjectId} embedded />
            </div>
          </div>
        )}

        {!loading && projects.length > 0 && !selectedProjectId && (
          <div className="fortknox-select-prompt">
            <p>Välj ett projekt ovan för att kompilera Fort Knox-rapport.</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default FortKnox
