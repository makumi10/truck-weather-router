import { LEVELS, LEVEL_COLOR, LEVEL_LABEL } from '../constants'
import { fmtHour } from '../format'

export default function HeatControls({ heatmap, hour, onHour, visible, onVisible }) {
  const start = new Date(heatmap.start).getTime()
  const when = new Date(start + hour * 3600e3)
  const ticks = [0, 12, 24, 36, 48]
  return (
    <div className="scrubber">
      <div className="scrub-head">
        <div className="scrub-when">
          <strong>{hour === 0 ? 'Now' : `In ${hour} h`}</strong>
          <span>{fmtHour(when)}</span>
        </div>
        <div className="legend">
          {LEVELS.map((l) => <span key={l}><i style={{ background: LEVEL_COLOR[l] }} />{LEVEL_LABEL[l]}</span>)}
        </div>
        <label className="switch">
          <input type="checkbox" checked={visible} onChange={(e) => onVisible(e.target.checked)} />
          <span className="track" /> Heatmap
        </label>
      </div>
      <input type="range" min="0" max={heatmap.hours} step="1" value={hour} disabled={!visible}
             onChange={(e) => onHour(Number(e.target.value))} aria-label="Forecast hour, 0 to 48" />
      <div className="ticks">
        {ticks.map((t) => <span key={t}>{t === 0 ? 'Now' : fmtHour(new Date(start + t * 3600e3))}</span>)}
      </div>
    </div>
  )
}
