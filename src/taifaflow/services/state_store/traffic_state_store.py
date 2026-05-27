from datetime import timezone
import json

from redis.asyncio import Redis

from taifaflow.models.events import CanonicalEventModel


class TrafficStateStore:
    """
    Redis key schema:

    - segment:{road_segment_id} (HASH)
      status, severity, confidence, last_updated, lat, lon, active_event_id, summary

    - segments:active (SET)
      member: road_segment_id

    - segment:{road_segment_id}:events (LIST)
      compact JSON of latest events, trimmed to MAX_EVENT_HISTORY
    """

    ACTIVE_SEGMENTS_KEY = "segments:active"
    MAX_EVENT_HISTORY = 50

    def __init__(self, redis_client: Redis) -> None:
        self.redis = redis_client

    def _segment_key(self, road_segment_id: str) -> str:
        return f"segment:{road_segment_id}"

    def _segment_events_key(self, road_segment_id: str) -> str:
        return f"segment:{road_segment_id}:events"

    async def upsert_segment_health(self, event: CanonicalEventModel) -> None:
        segment_key = self._segment_key(event.road_segment_id)
        event_list_key = self._segment_events_key(event.road_segment_id)

        status = self._status_from_severity(event.severity.value)
        last_updated = event.timestamp.astimezone(timezone.utc).isoformat()

        await self.redis.hset(
            segment_key,
            mapping={
                "status": status,
                "severity": event.severity.value,
                "confidence": event.confidence,
                "last_updated": last_updated,
                "lat": event.location.latitude,
                "lon": event.location.longitude,
                "active_event_id": event.event_id,
                "summary": event.summary,
            },
        )

        await self.redis.sadd(self.ACTIVE_SEGMENTS_KEY, event.road_segment_id)

        compact_event = json.dumps(
            {
                "event_id": event.event_id,
                "severity": event.severity.value,
                "confidence": event.confidence,
                "timestamp": last_updated,
                "summary": event.summary,
            }
        )
        await self.redis.lpush(event_list_key, compact_event)
        await self.redis.ltrim(event_list_key, 0, self.MAX_EVENT_HISTORY - 1)

    async def get_segment_health(self, road_segment_id: str) -> dict[str, str]:
        data = await self.redis.hgetall(self._segment_key(road_segment_id))
        return {k.decode("utf-8"): v.decode("utf-8") for k, v in data.items()}

    @staticmethod
    def _status_from_severity(severity: str) -> str:
        mapping = {
            "low": "clear",
            "medium": "slow",
            "high": "congested",
            "critical": "blocked",
        }
        return mapping.get(severity, "slow")
