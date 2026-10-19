const API = import.meta.env.VITE_API_URL ?? ''
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function planOnce(payload) {
  let res
  try {
    res = await fetch(`${API}/api/plan/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch {
    const err = new Error('Could not reach the server. Check your connection and try again.')
    err.retryable = true
    throw err
  }
  let data = null
  try { data = await res.json() } catch { /* non-JSON error page */ }
  if (!res.ok) {
    const detail = data?.details ? Object.values(data.details).flat().join(' ') : ''
    const err = new Error(data?.error ? `${data.error}${detail ? ': ' + detail : ''}` : `Request failed (${res.status})`)
    // Upstream hiccups (weather/routing busy) and a waking server are worth retrying; bad input is not.
    err.retryable = [502, 503, 504].includes(res.status)
    throw err
  }
  return data
}

// Retries transient failures up to 3 times. The backend caches every weather batch that succeeded,
// so each retry is faster than the last.
export async function planTrip(payload) {
  const attempts = 3
  for (let i = 0; i < attempts; i += 1) {
    try {
      return await planOnce(payload)
    } catch (err) {
      if (!err.retryable || i === attempts - 1) throw err
      await sleep(1500 * (i + 1))
    }
  }
  return null
}

// Wakes a sleeping free-tier API while the user is still typing. Failures are ignored.
export function warmUp() {
  fetch(`${API}/api/health/`).catch(() => {})
}
