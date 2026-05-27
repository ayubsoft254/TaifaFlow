from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceKind(str, Enum):
    maps = "maps"
    radio = "radio"
    social = "social"
    crowd = "crowd"


class SeverityLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class GeoPoint(BaseModel):
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class CanonicalEventModel(BaseModel):
    event_id: str = Field(min_length=3)
    source: SourceKind
    location: GeoPoint
    road_segment_id: str = Field(min_length=2)
    severity: SeverityLevel
    timestamp: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=3)
    metadata: dict[str, Any] = Field(default_factory=dict)
