import { apiUrl } from './api'

export async function pollJob(jobId, { auth, intervalMs = 1000, timeoutMs = 180000 } = {}) {
  const deadline = Date.now() + timeoutMs

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const res = await fetch(apiUrl(`/jobs/${jobId}`), {
      headers: auth ? { 'Authorization': `Basic ${auth}` } : undefined
    })
    if (!res.ok) {
      throw new Error(`Kunde inte hämta jobb (HTTP ${res.status})`)
    }
    const job = await res.json()
    const status = String(job.status || '')

    if (status === 'succeeded' || status === 'failed') {
      return job
    }

    if (Date.now() > deadline) {
      throw new Error('Jobbet tog för lång tid')
    }

    await new Promise((r) => setTimeout(r, intervalMs))
  }
}

