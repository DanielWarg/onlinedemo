import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { Menu, Settings } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import ProjectsList from './pages/ProjectsList'
import ProjectDetail from './pages/ProjectDetail'
import DocumentView from './pages/DocumentView'
import Scout from './pages/Scout'
import FortKnox from './pages/FortKnox'
import Intro from './pages/Intro'
import Sidebar from './components/Sidebar'
import './index.css'

function App() {
  const [demoMode, setDemoMode] = useState(false)
  const [darkMode, setDarkMode] = useState(true)

  useEffect(() => {
    // Set dark mode as default
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    
    const apiBase = import.meta.env.VITE_API_URL || 
      (import.meta.env.DEV ? 'http://localhost:8000' : '')
    
    fetch(`${apiBase}/health`)
      .then(res => res.json())
      .then(data => {
        setDemoMode(data.demo_mode || false)
      })
      .catch(() => {})
  }, [darkMode])

  const toggleTheme = () => {
    setDarkMode(!darkMode)
  }

  return (
    <Router>
      <AppContent demoMode={demoMode} darkMode={darkMode} toggleTheme={toggleTheme} />
    </Router>
  )
}

function AppContent({ demoMode, darkMode, toggleTheme }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const currentDate = new Date().toLocaleDateString('sv-SE', { 
    weekday: 'long', 
    day: 'numeric', 
    month: 'long' 
  })

  return (
    <div className="app-layout">
      <div
        className={`sidebar-backdrop ${sidebarOpen ? 'open' : ''}`}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      <Sidebar
        darkMode={darkMode}
        toggleTheme={toggleTheme}
        mobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
      />
      
      <main className="main-content">
        <header className="top-header">
          <div className="header-left">
            <button
              className="header-menu-btn"
              onClick={() => setSidebarOpen(true)}
              aria-label="Öppna meny"
              type="button"
            >
              <Menu size={18} />
            </button>
            <div className="header-date">{currentDate}</div>
          </div>
          
          <div className="header-right">
            {demoMode && (
              <div className="demo-badge">
                Demo (skyddad)
              </div>
            )}
            <button 
              className="header-settings-btn"
              title="Inställningar"
              disabled
            >
              <Settings size={18} />
            </button>
          </div>
        </header>
        
        <div className="content-area">
          <Routes>
            <Route path="/" element={<Intro />} />
            <Route path="/intro" element={<Intro />} />
            <Route path="/projects" element={<ProjectsList />} />
            <Route path="/projects/:id" element={<ProjectDetail />} />
            <Route path="/projects/:projectId/documents/:documentId" element={<DocumentView />} />
            <Route path="/scout" element={<Scout />} />
            <Route path="/fortknox" element={<FortKnox />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}

export default App

