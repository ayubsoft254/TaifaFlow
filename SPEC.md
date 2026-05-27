# TaifaFlow Technical Specification (Initial Implementation)

## 1. Purpose

TaifaFlow is an intelligent traffic orchestration platform ("Traffic Brain") that ingests multimodal signals and continuously recommends safer, faster, and more balanced routing choices.

This specification defines the initial implementation baseline for:

- modular FastAPI backend architecture
- canonical event normalization
- Redis-backed real-time traffic state
- Observe-Think-Act agentic loop scaffolding
- HTMX/Tailwind dashboard rendering

## 2. Architecture Overview

### Backend

- Framework: FastAPI
- Templating: Jinja2 templates from `src/templates`
- State:
  - Redis for live road segment state
  - PostgreSQL reserved for historical persistence (future iteration)
- Reasoning engine:
  - `Observe -> Think -> Act` service boundary in `services/orchestration`

### Frontend

- HTMX for incremental HTML swaps and live update hooks
- Tailwind CSS (CDN for bootstrap phase)
- Single dashboard page served by FastAPI

## 3. Project Structure

```text
TaifaFlow/
  README.md
  SPEC.md
  src/
    taifaflow/
      __init__.py
      config.py
      main.py
      api/
        __init__.py
        routes/
          __init__.py
          dashboard.py
      models/
        __init__.py
        events.py
      services/
        __init__.py
        ingestion/
          __init__.py
          pipeline.py
        orchestration/
          __init__.py
          brain.py
        state_store/
          __init__.py
          traffic_state_store.py
    templates/
      dashboard.html
```

## 4. Canonical Event Model

All upstream sources (Maps, radio transcripts, social posts, crowdsourced reports) are normalized into a common contract.

### Model: `CanonicalEventModel`

| Field | Type | Required | Description |
|---|---|---:|---|
| `event_id` | `str` | yes | Stable event id (`evt_*` or UUID) |
| `source` | `SourceKind` | yes | Event origin (`maps`, `radio`, `social`, `crowd`) |
| `location` | `GeoPoint` | yes | Latitude and longitude |
| `road_segment_id` | `str` | yes | Logical road segment key |
| `severity` | `SeverityLevel` | yes | Incident intensity (`low`, `medium`, `high`, `critical`) |
| `timestamp` | `datetime` | yes | Event occurrence or detection time (UTC) |
| `confidence` | `float` | yes | Score in range `[0.0, 1.0]` |
| `summary` | `str` | yes | Human-readable event text |
| `metadata` | `dict[str, Any]` | no | Source-specific payload details |

Validation constraints:

- `confidence` is clamped/validated to [0.0, 1.0]
- `latitude` in [-90, 90], `longitude` in [-180, 180]
- `summary` should be concise and non-empty

## 5. Redis Schema (TrafficStateStore)

The real-time segment health cache uses namespaced keys:

### Primary Segment Hash

- Key pattern: `segment:{road_segment_id}`
- Type: Redis Hash

Fields:

- `status`: `clear | slow | congested | blocked`
- `severity`: `low | medium | high | critical`
- `confidence`: normalized score
- `last_updated`: ISO8601 UTC timestamp
- `lat`: representative centroid latitude
- `lon`: representative centroid longitude
- `active_event_id`: last dominant event id
- `summary`: latest event summary

### Active Segment Set

- Key: `segments:active`
- Type: Redis Set
- Members: `road_segment_id` values currently being tracked

### Event Trace List (Optional Rolling Context)

- Key pattern: `segment:{road_segment_id}:events`
- Type: Redis List
- Entry format: compact JSON for latest normalized events
- Retention: trim to latest N records (for example, 50)

## 6. Observe-Think-Act Loop

### Observe

- pull normalized events from ingestion pipeline
- read current segment states from Redis
- (future) call Maps API adapter for traffic overlays

### Think

- compare fresh signals with baseline segment health
- compute deltas and identify impacted routes
- decide if UI-facing alert state changed

### Act

- update Redis segment health
- expose HTML fragment endpoints for HTMX swaps (next phase)
- publish routing/alert recommendations to clients

## 7. Initial API Contract

### Implemented Now

- `GET /`
  - returns dashboard HTML (`dashboard.html`)
  - includes map container and live-alert region (`#traffic-alert-box`)

### Planned Next

- `GET /fragments/traffic-alerts`
  - returns an HTML partial targeted by HTMX (`#traffic-alert-box`)
- `GET /stream/alerts` (SSE)
  - optional push-based updates for low-latency UI refresh

## 8. Non-Functional Baseline

- Python 3.11+
- Redis network failures should degrade gracefully
- Use UTC timestamps internally
- Keep ingestion adapters isolated per source
