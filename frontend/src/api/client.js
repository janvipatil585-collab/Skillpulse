const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL
const developmentBaseUrl = import.meta.env.DEV ? 'http://localhost:8000' : ''
const API_BASE_URL = (configuredBaseUrl || developmentBaseUrl).replace(/\/$/, '')

export function buildQuery(filters = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  }
  return params.toString()
}

export async function apiGet(path, filters = {}, options = {}) {
  if (!API_BASE_URL) {
    throw new Error('VITE_API_BASE_URL must be set to the deployed FastAPI URL for production builds.')
  }
  const query = buildQuery(filters)
  const url = `${API_BASE_URL}${path}${query ? `?${query}` : ''}`
  const response = await fetch(url, { signal: options.signal })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`API ${response.status}: ${detail || response.statusText}`)
  }
  return response.json()
}

export { API_BASE_URL }