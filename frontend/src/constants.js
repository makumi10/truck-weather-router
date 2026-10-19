export const LEVELS = ['low', 'moderate', 'high', 'severe', 'no_travel']
export const LEVEL_LABEL = {
  low: 'Low', moderate: 'Moderate', high: 'High', severe: 'Severe', no_travel: 'No Travel',
}
export const LEVEL_COLOR = {
  low: '#2e9e5b', moderate: '#d9a400', high: '#f08a24', severe: '#d6342c', no_travel: '#6b1fa0',
}
// Heatmap intensity per risk level index (0 = low draws nothing).
export const HEAT_WEIGHT = [0, 0.3, 0.55, 0.8, 1]
export const ROUTE_COLORS = { A: '#2563eb', B: '#0891b2', C: '#c026d3' }
