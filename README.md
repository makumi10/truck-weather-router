# Weather-Aware Truck Routing

React + Django app that generates three route options for a truck, samples the forecast at the
truck's **estimated arrival time** at each checkpoint, scores weather risk with the load rules,
and recommends the route that balances risk and travel time. Includes a 0–48 h weather heatmap.

- **Live app:** _<add Vercel URL>_  (the API sleeps on Render's free tier; first request may take ~30 s)
- **API:** _<add Render URL>_`/api/health/`
- **Walkthrough:** _<add Loom URL>_

## Stack
| Layer | Choice | Why |
|---|---|---|
| Backend | Django 6.1 + DRF, numpy, pytest | Small, testable; numpy for polyline math |
| Routing | OSRM (`alternatives=3`) | Free, no key |
| Geocoding | Nominatim (OSM) | Free, no key; accepts `lat,lng` too |
| Weather | Open-Meteo | Free, no key, hourly 0–96 h, many coordinates per request |
| Frontend | React 18 + Vite, Leaflet / react-leaflet, leaflet.heat | Light, fast, no map token |

## How it works
```
form ─► POST /api/plan/
          geocode (Nominatim) ─► 3 routes (OSRM, via-point fallback, de-duplicated)
          per route: checkpoints every 10/25/50 mi ─► ETA = departure + duration × (mile / length)
          ONE batched, cached Open-Meteo fetch for all checkpoints + heatmap grid
          nearest forecast hour to each ETA ─► risk.classify(wind, rain, snow, load)
          scoring.score_route ─► rank_routes ─► recommendation + reason string
          heatmap: 49 hourly risk levels per grid point
        ◄─ JSON (routes, checkpoints, recommendation, heatmap)
slider ─► changes an hour index client-side only (no network calls)
```
Code map: `backend/routing/` — `risk.py` (rules), `scoring.py` (miles/avg/ranking), `planner.py`
(pipeline), `osrm.py`, `weather.py`, `geocode.py`, `geo.py`, `views.py`. Frontend: `frontend/src/`.

## Risk rules (as implemented)
| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | <25 | 25–34 | 35–44 | 45–54 | ≥55 |
| Rain (in/hr) | <0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
| Snow (in/hr) | <0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 |

Load rules: wind ≥55 → No Travel (any load); wind 45–54 and load >30,000 lb → No Travel;
wind 35–44 and load >40,000 lb → Severe. A checkpoint's level is the **worst** of wind, rain, snow
after the load rules. Ranges include their lower bound (exactly 0.25 in/hr rain = High; exactly 1.00 = Severe).

## Recommendation
Each checkpoint owns the miles halfway to its neighbours, so risk is measured in **miles**, not points.
Routes are sorted by: **No Travel miles → Severe miles → High miles → average risk → travel time**
(whole miles; average risk to 2 dp). The API returns a plain-English reason for the winner.

## Assumptions & decisions
1. **10 / 25 / 50 mile sampling** is a dropdown, plus *Auto* (10 mi <150 mi trips, 25 mi <500, 50 mi beyond). Capped at 300 checkpoints per route.
2. **No Travel miles are the first ranking key.** The brief lists Severe first, but No Travel is worse than Severe.
3. **ETA** assumes constant average speed per route (OSRM total duration scaled by distance). `TRUCK_TIME_FACTOR` env var can slow it for trucks (default 1.0).
4. **Wind** uses sustained 10 m speed, not gusts. **Rain** = rain + showers (in/hr). **Snow** = snowfall (in/hr).
5. **Forecast window:** Open-Meteo data is fetched for 3 days; an ETA outside it uses the nearest hour and is flagged in the UI. The heatmap covers now → +48 h.
6. Times: the browser sends departure in UTC; the UI shows local time.
7. **Routing is car-profile** (public OSRM has no truck profile): no height/weight restrictions. Stated as a limitation, not hidden.
8. Heatmap shows hazard only (Low draws nothing) so calm areas stay clear; weights are Moderate .3 / High .55 / Severe .8 / No Travel 1.0.

## Run locally
```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest                      # 74 tests
python manage.py runserver  # http://localhost:8000

# frontend (new terminal)
cd frontend
npm install
npm run dev                 # http://localhost:5173 (proxies /api to Django)
```
Quick API check:
```bash
curl -X POST http://localhost:8000/api/plan/ -H 'Content-Type: application/json' -d '{
  "origin":"Chicago, IL","destination":"Denver, CO",
  "departure":"2026-10-21T14:00:00Z","load_weight_lb":42000,"checkpoint_spacing":"auto"}'
```

## Performance
A plan makes live calls to free public services (Nominatim is limited to 1 req/s, OSRM's demo server, Open-Meteo).
Weather for all checkpoints and the heatmap grid is fetched in parallel batches and cached 30 min; geocoding is cached
24 h and routes 1 h, so repeating a trip is near-instant. Responses are gzip-compressed. Every plan response includes a
`timings` object (geocode / routing / weather / scoring / heatmap, in ms) and logs it, which makes slow stages easy to spot.

## Reliability
The free upstream APIs can rate-limit or time out, so the weather client is defensive: batches of 50 locations, modest
parallelism, 3 attempts with exponential backoff, and every successful batch is cached immediately (30 min fresh, 12 h stale).
If a batch still fails, the last known forecast for those points is used; small gaps borrow the nearest available point
(within 60 mi) and the UI shows a short notice. Larger gaps return a 502, and the frontend retries automatically, which is
fast because everything already fetched is cached. See `routing/weather.py` and `test_weather.py`.

## Tests
`pytest` in `backend/` covers every threshold boundary and load rule (`test_risk.py`), the ranking
priorities (`test_scoring.py`), polyline/sampling math, forecast-hour selection and clamping,
the full planner with routing/weather mocked (calm → fastest; severe-but-faster route avoided;
load changes severity; heatmap shape), and the API contract.

## Deploy
**Backend (Render):** New → Blueprint → select this repo (uses `render.yaml`). After the frontend is live,
set `CORS_ALLOWED_ORIGINS` to its URL. Health check: `/api/health/`.
**Frontend (Vercel):** Import repo, Root Directory `frontend`, env var `VITE_API_URL=https://<your-render-service>.onrender.com`.
The frontend pings `/api/health/` on page load to wake a sleeping instance. To avoid cold starts entirely, add a free uptime monitor
(e.g. UptimeRobot) that requests `https://<service>.onrender.com/api/health/` every 5–10 minutes.
If geocoding is throttled from Render's shared IPs, set `HTTP_USER_AGENT` to include a contact email (Nominatim policy).

## Limitations / next steps
OSRM car routing (swap in a truck-aware provider via `osrm.py`); gust-based wind; per-segment speed
profiles for more precise ETAs; persistent weather cache (Redis) for multi-worker deploys.
