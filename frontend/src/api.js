const API = import.meta.env.VITE_API_URL ?? ''

export async function planTrip(payload) {
  const res = await fetch(`${API}/api/plan/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  let data = null
  try { data = await res.json() } catch { /* non-JSON error page */ }
  if (!res.ok) {
    const detail = data?.details ? Object.values(data.details).flat().join(' ') : ''
    throw new Error(data?.error ? `${data.error}${detail ? ': ' + detail : ''}` : `Request failed (${res.status})`)
  }
  return data
}

// Wakes a sleeping free-tier API while the user is still typing. Failures are ignored.
export function warmUp() {
  fetch(`${API}/api/health/`).catch(() => {})
}
