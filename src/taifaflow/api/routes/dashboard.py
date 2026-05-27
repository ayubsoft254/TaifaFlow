from pathlib import Path
import asyncio
from collections.abc import AsyncIterator
from datetime import datetime

from redis.asyncio import Redis

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from taifaflow.config import settings
from taifaflow.services.state_store.traffic_state_store import TrafficStateStore


BASE_DIR = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

DEFAULT_ALERT = "No major disruptions detected."
SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_redis_client: Redis | None = None


def _get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _format_sse(event: str, data: str) -> str:
    lines = data.splitlines() or [""]
    payload = [f"event: {event}"]
    payload.extend(f"data: {line}" for line in lines)
    payload.append("")
    return "\n".join(payload) + "\n"


async def _current_alert_context() -> dict[str, str]:
    fallback = {
        "alert_title": "Traffic Alerts",
        "alert_text": DEFAULT_ALERT,
        "alert_severity": "low",
        "alert_updated": "",
    }

    try:
        redis_client = _get_redis_client()
        active_segments = await redis_client.smembers(TrafficStateStore.ACTIVE_SEGMENTS_KEY)
    except Exception:
        return fallback

    if not active_segments:
        return fallback

    strongest: dict[str, str] | None = None
    strongest_rank = -1
    strongest_time = datetime.min

    for segment_id in active_segments:
        segment_data = await redis_client.hgetall(f"segment:{segment_id}")
        if not segment_data:
            continue

        severity = segment_data.get("severity", "low")
        rank = SEVERITY_RANK.get(severity, 0)
        raw_updated = segment_data.get("last_updated", "")
        try:
            updated_at = datetime.fromisoformat(raw_updated.replace("Z", "+00:00")) if raw_updated else datetime.min
        except ValueError:
            updated_at = datetime.min

        if strongest is None or rank > strongest_rank or (rank == strongest_rank and updated_at > strongest_time):
            strongest = segment_data
            strongest_rank = rank
            strongest_time = updated_at

    if strongest is None:
        return fallback

    alert_summary = strongest.get("summary") or DEFAULT_ALERT
    last_updated = strongest.get("last_updated", "")
    severity = strongest.get("severity", "low")

    return {
        "alert_title": "Traffic Alerts",
        "alert_text": alert_summary,
        "alert_severity": severity,
        "alert_updated": last_updated,
    }


async def _render_alert_fragment() -> str:
    context = await _current_alert_context()
    template = templates.get_template("fragments/traffic_alert_box.html")
    return template.render(**context)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "page_title": "TaifaFlow Traffic Brain",
            "initial_alert": DEFAULT_ALERT,
        },
    )


@router.get("/fragments/traffic-alert-box", response_class=HTMLResponse)
async def traffic_alert_box_fragment() -> HTMLResponse:
    return HTMLResponse(content=await _render_alert_fragment())


@router.get("/stream/traffic-alerts")
async def stream_traffic_alerts(request: Request) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        last_fragment = ""
        while True:
            if await request.is_disconnected():
                break

            fragment = await _render_alert_fragment()
            if fragment != last_fragment:
                last_fragment = fragment
                yield _format_sse("traffic-alert", fragment)
            else:
                yield ": keep-alive\n\n"

            await asyncio.sleep(3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
