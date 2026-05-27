from datetime import datetime, timezone
from typing import Any

from taifaflow.models.events import CanonicalEventModel, GeoPoint, SeverityLevel, SourceKind


class IngestionPipeline:
    """Normalizes raw source payloads into CanonicalEventModel."""

    def normalize(self, raw_event: dict[str, Any]) -> CanonicalEventModel:
        return CanonicalEventModel(
            event_id=str(raw_event.get("event_id", f"evt_{int(datetime.now(tz=timezone.utc).timestamp())}")),
            source=SourceKind(raw_event.get("source", "crowd")),
            location=GeoPoint(
                latitude=float(raw_event.get("latitude", 0.0)),
                longitude=float(raw_event.get("longitude", 0.0)),
            ),
            road_segment_id=str(raw_event.get("road_segment_id", "unknown-segment")),
            severity=SeverityLevel(raw_event.get("severity", "low")),
            timestamp=raw_event.get("timestamp", datetime.now(tz=timezone.utc)),
            confidence=float(raw_event.get("confidence", 0.5)),
            summary=str(raw_event.get("summary", "Unclassified traffic signal")),
            metadata=raw_event.get("metadata", {}),
        )
