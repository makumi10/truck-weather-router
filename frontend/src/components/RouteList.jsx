import { LEVELS, LEVEL_COLOR, LEVEL_LABEL, ROUTE_COLORS } from '../constants'
import { fmtDuration, fmtTime } from '../format'

function RiskBar({ miles, total }) {
  return (
    <div className="riskbar" role="img" aria-label="Miles at each risk level">
      {LEVELS.map((l) => miles[l] > 0 && (
        <span key={l} title={`${LEVEL_LABEL[l]}: ${Math.round(miles[l])} mi`}
              style={{ width: `${(miles[l] / total) * 100}%`, background: LEVEL_COLOR[l] }} />
      ))}
    </div>
  )
}

export default function RouteList({ result, selected, onSelect }) {
  const rec = result.recommendation
  return (
    <section className="results">
      <div className="verdict">
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="#1b8a4b" /><path d="M7 12.5l3.2 3.2L17 9" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <div>
          <h2>Route {rec.label} is the safest choice</h2>
          <p>{rec.reason}</p>
        </div>
      </div>

      <ul className="routes">
        {result.routes.map((r) => {
          const s = r.summary
          const m = s.miles_by_level
          const active = selected === r.label
          return (
            <li key={r.label}>
              <button className={`route ${active ? 'active' : ''}`} onClick={() => onSelect(r.label)} aria-pressed={active}>
                <span className="stripe" style={{ background: ROUTE_COLORS[r.label] }} />
                <div className="route-main">
                  <div className="route-top">
                    <span className="route-name">Route {r.label}</span>
                    {r.recommended && <span className="tag best">Recommended</span>}
                    <span className="tag" style={{ '--c': LEVEL_COLOR[s.worst_level] }}>
                      <i /> Worst: {LEVEL_LABEL[s.worst_level]}
                    </span>
                  </div>
                  <div className="route-time">
                    <strong>{fmtDuration(s.duration_s)}</strong>
                    <span>{Math.round(s.distance_mi)} mi</span>
                    <span>Arrive {fmtTime(s.arrival)}</span>
                  </div>
                  <RiskBar miles={m} total={s.distance_mi || 1} />
                  {active && (
                    <div className="detail">
                      <ul className="miles">
                        {LEVELS.filter((l) => m[l] > 0).map((l) => (
                          <li key={l}><i style={{ background: LEVEL_COLOR[l] }} />{LEVEL_LABEL[l]}<b>{Math.round(m[l])} mi</b></li>
                        ))}
                      </ul>
                      <p>Average risk {s.avg_risk.toFixed(2)} of 4. {r.checkpoints.length} weather checkpoints, one every {r.checkpoint_spacing_mi} mi.</p>
                      {s.forecast_clamped && <p className="warn">Some arrival times fall past the forecast window, so the last available hour was used.</p>}
                    </div>
                  )}
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
