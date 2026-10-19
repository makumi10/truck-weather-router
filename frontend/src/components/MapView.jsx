import { useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, ZoomControl, useMap } from 'react-leaflet'
import { HEAT_WEIGHT, LEVEL_COLOR, LEVEL_LABEL, ROUTE_COLORS } from '../constants'
import { fmtTime } from '../format'

const OSM = { url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '© OpenStreetMap contributors' }
const ESRI = {
  url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
  attribution: 'Tiles © Esri',
}
const pin = (cls, label) => L.divIcon({
  className: 'pin-wrap', iconSize: [30, 38], iconAnchor: [15, 36], popupAnchor: [0, -32],
  html: `<div class="pin ${cls}"><span>${label}</span></div>`,
})
const START_PIN = pin('start', 'A')
const END_PIN = pin('end', 'B')
const GRADIENT = { 0.0: '#2e9e5b', 0.3: '#d9a400', 0.55: '#f08a24', 0.8: '#d6342c', 1.0: '#6b1fa0' }

function FitBounds({ routes }) {
  const map = useMap()
  useEffect(() => {
    const pts = routes.flatMap((r) => r.geometry)
    if (pts.length) map.fitBounds(pts, { paddingTopLeft: [window.innerWidth > 900 ? 450 : 30, 40], paddingBottomRight: [40, window.innerWidth > 900 ? 150 : 40] })
  }, [routes, map])
  return null
}

// leaflet.heat is a UMD plugin that expects window.L, so it is loaded lazily after L is exposed.
// The layer is created once; the slider only calls setLatLngs (no network, no re-creation).
function HeatLayer({ points, hour, visible }) {
  const map = useMap()
  const layerRef = useRef(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    window.L = L
    import('leaflet.heat').then(() => !cancelled && setReady(true))
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!ready) return undefined
    const layer = L.heatLayer([], { radius: 34, blur: 26, max: 1, minOpacity: 0.35, maxZoom: 9, gradient: GRADIENT })
    layerRef.current = layer
    return () => { map.removeLayer(layer); layerRef.current = null }
  }, [ready, map])

  const data = useMemo(
    () => points.map(([lat, lng, levels]) => [lat, lng, HEAT_WEIGHT[levels[hour]]]).filter((p) => p[2] > 0),
    [points, hour],
  )

  useEffect(() => {
    const layer = layerRef.current
    if (!layer) return
    if (!visible) { map.removeLayer(layer); return }
    if (!map.hasLayer(layer)) layer.addTo(map)
    layer.setLatLngs(data)
  }, [ready, visible, data, map])

  return null
}

export default function MapView({ result, selected, onSelect, hour, heatVisible }) {
  const [tiles, setTiles] = useState(OSM)
  const errors = useRef(0)
  const routes = result?.routes ?? []
  // Draw the selected route last so it sits on top.
  const ordered = useMemo(() => [...routes].sort((a, b) => (a.label === selected) - (b.label === selected)), [routes, selected])

  const onTileError = () => {
    errors.current += 1
    if (errors.current === 6 && tiles === OSM) setTiles(ESRI) // fall back if OSM tiles are blocked/throttled
  }

  return (
    <MapContainer center={[39.5, -98.35]} zoom={4} preferCanvas zoomControl={false} className="map">
      <ZoomControl position="bottomright" />
      <TileLayer key={tiles.url} url={tiles.url} attribution={tiles.attribution} eventHandlers={{ tileerror: onTileError }} />
      {result && <FitBounds routes={routes} />}

      {ordered.map((r) => {
        const sel = r.label === selected
        return (
          <Polyline key={`${r.label}-casing`} positions={r.geometry} interactive={false}
                    pathOptions={{ color: '#fff', weight: sel ? 11 : 7, opacity: sel ? 1 : 0.7 }} />
        )
      })}
      {ordered.map((r) => (
        <Polyline key={r.label} positions={r.geometry} eventHandlers={{ click: () => onSelect(r.label) }}
                  pathOptions={{ color: ROUTE_COLORS[r.label], weight: r.label === selected ? 6 : 4,
                                 opacity: r.label === selected ? 1 : 0.6 }} />
      ))}

      {ordered.map((r) => r.checkpoints.map((c, i) => {
        const sel = r.label === selected
        return (
          <CircleMarker key={`${r.label}-${i}`} center={[c.lat, c.lng]} radius={sel ? 6 : 3.5}
                        pathOptions={{ color: '#fff', weight: sel ? 2 : 1.5, fillColor: LEVEL_COLOR[c.level_name],
                                       fillOpacity: sel ? 1 : 0.7 }}>
            <Popup>
              <div className="popup">
                <strong>Route {r.label}, mile {c.mile}</strong>
                <div><span className="tag" style={{ '--c': LEVEL_COLOR[c.level_name] }}><i /> {LEVEL_LABEL[c.level_name]} risk</span></div>
                <div className="eta">Arrive {fmtTime(c.eta)}</div>
                <dl><dt>Wind</dt><dd>{c.wind_mph} mph</dd><dt>Rain</dt><dd>{c.rain_in_hr} in/hr</dd><dt>Snow</dt><dd>{c.snow_in_hr} in/hr</dd></dl>
                <div className="muted">{c.reason}</div>
                {c.forecast_clamped && <div className="warn">Arrival is past the forecast window, so the last available hour was used.</div>}
              </div>
            </Popup>
          </CircleMarker>
        )
      }))}

      {result && (
        <>
          <Marker position={[result.request.origin.lat, result.request.origin.lng]} icon={START_PIN}>
            <Popup>{result.request.origin.name}</Popup>
          </Marker>
          <Marker position={[result.request.destination.lat, result.request.destination.lng]} icon={END_PIN}>
            <Popup>{result.request.destination.name}</Popup>
          </Marker>
          <HeatLayer points={result.heatmap.points} hour={hour} visible={heatVisible} />
        </>
      )}
    </MapContainer>
  )
}
