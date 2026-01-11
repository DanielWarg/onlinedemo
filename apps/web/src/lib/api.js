// Central API base for both dev and prod.
// - Dev default: http://localhost:8000/api
// - Prod (Tailscale/Caddy): VITE_API_BASE=/api

const rawBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'
export const API_BASE = String(rawBase).replace(/\/+$/, '')

export function apiUrl(path = '') {
  const p = String(path || '')
  if (!p) return API_BASE
  return `${API_BASE}${p.startsWith('/') ? p : `/${p}`}`
}

