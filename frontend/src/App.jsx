import { useEffect, useState } from 'react'
import { planTrip, warmUp } from './api'
import PlanForm from './components/PlanForm'
import RouteList from './components/RouteList'
import MapView from './components/MapView'
import HeatControls from './components/HeatControls'
import { fmtTime } from './format'

const Logo = () => (
  <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">
    <rect width="32" height="32" rx="8" fill="#12202e" />
    <path d="M6 20V11h11v9M17 14h5l3 3v3H17" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinejoin="round" />
    <circle cx="11" cy="21" r="2.2" fill="#12202e" stroke="#fff" strokeWidth="1.8" />
    <circle cx="21" cy="21" r="2.2" fill="#12202e" stroke="#fff" strokeWidth="1.8" />
  </svg>
)

export default function App() {
  const [result, setResult] = useState(null)
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hour, setHour] = useState(0)
  const [heatVisible, setHeatVisible] = useState(true)
  const [editing, setEditing] = useState(true)

  useEffect(() => { warmUp() }, [])

  const submit = async (payload) => {
    setLoading(true); setError(null)
    try {
      const data = await planTrip(payload)
      setResult(data)
      setSelected(data.recommendation.label)
      setHour(0)
      setEditing(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const req = result?.request
  const collapsed = result && !editing

  return (
    <div className="app">
      <MapView result={result} selected={selected} onSelect={setSelected} hour={hour} heatVisible={heatVisible} />

      <aside className="panel">
        <header className="brand">
          <Logo />
          <div>
            <h1>Truck Weather Routing</h1>
            <p>Safest route by weather, load and time</p>
          </div>
        </header>

        {loading && <div className="progress" role="status" aria-label="Finding routes" />}

        <div className="panel-body">
          {collapsed && (
            <div className="summary">
              <div className="summary-trip">
                <strong>{req.origin.query}</strong>
                <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M5 12h14m-5-5l5 5-5 5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                <strong>{req.destination.query}</strong>
              </div>
              <div className="summary-meta">
                <span>Leaves {fmtTime(req.departure)}</span>
                <span>{req.load_weight_lb.toLocaleString()} lb load</span>
              </div>
              <button className="link" onClick={() => setEditing(true)}>Edit trip</button>
            </div>
          )}

          <div hidden={collapsed}>
            <PlanForm onSubmit={submit} loading={loading} />
          </div>

          {error && <div className="error" role="alert">{error}</div>}
          {result?.warnings?.length > 0 && (
            <div className="warning" role="status">{result.warnings.join(' ')}</div>
          )}
          {result && <RouteList result={result} selected={selected} onSelect={setSelected} />}
        </div>
      </aside>

      {result && (
        <HeatControls heatmap={result.heatmap} hour={hour} onHour={setHour}
                      visible={heatVisible} onVisible={setHeatVisible} />
      )}
    </div>
  )
}
