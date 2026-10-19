import { useState } from 'react'
import { localInputValue } from '../format'

const defaultDeparture = () => {
  const d = new Date(Date.now() + 3600e3)
  d.setMinutes(0, 0, 0)
  return localInputValue(d)
}

export default function PlanForm({ onSubmit, loading }) {
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [departure, setDeparture] = useState(defaultDeparture)
  const [load, setLoad] = useState(42000)
  const [spacing, setSpacing] = useState('auto')

  const submit = (e) => {
    e.preventDefault()
    onSubmit({
      origin: origin.trim(),
      destination: destination.trim(),
      departure: new Date(departure).toISOString(), // local input -> UTC for the backend
      load_weight_lb: Number(load),
      checkpoint_spacing: spacing,
    })
  }

  return (
    <form className="form" onSubmit={submit}>
      <div className="endpoints">
        <div className="rail" aria-hidden="true"><i className="rail-from" /><i className="rail-line" /><i className="rail-to" /></div>
        <div className="fields">
          <input required aria-label="Origin" value={origin} onChange={(e) => setOrigin(e.target.value)} placeholder="Choose starting point" />
          <input required aria-label="Destination" value={destination} onChange={(e) => setDestination(e.target.value)} placeholder="Choose destination" />
        </div>
      </div>

      <div className="grid2">
        <label>Departure
          <input type="datetime-local" required value={departure} onChange={(e) => setDeparture(e.target.value)} />
        </label>
        <label>Load weight
          <span className="unit">
            <input type="number" min="0" max="200000" step="500" required value={load} onChange={(e) => setLoad(e.target.value)} />
            <em>lb</em>
          </span>
        </label>
      </div>

      <label>Weather check every
        <select value={spacing} onChange={(e) => setSpacing(e.target.value)}>
          <option value="auto">Auto (by trip length)</option>
          <option value="10">10 miles</option>
          <option value="25">25 miles</option>
          <option value="50">50 miles</option>
        </select>
      </label>

      <button type="submit" className="primary" disabled={loading}>
        {loading ? 'Finding routes…' : 'Find safest route'}
      </button>
    </form>
  )
}
