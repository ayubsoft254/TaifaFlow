from collections.abc import Sequence

from taifaflow.models.events import CanonicalEventModel
from taifaflow.services.state_store.traffic_state_store import TrafficStateStore


class ObserveThinkActBrain:
    """Scaffold for the Observe-Think-Act control loop."""

    def __init__(self, state_store: TrafficStateStore) -> None:
        self.state_store = state_store

    async def observe(self, events: Sequence[CanonicalEventModel]) -> Sequence[CanonicalEventModel]:
        return events

    async def think(self, events: Sequence[CanonicalEventModel]) -> list[CanonicalEventModel]:
        return [event for event in events if event.confidence >= 0.5]

    async def act(self, events: Sequence[CanonicalEventModel]) -> None:
        for event in events:
            await self.state_store.upsert_segment_health(event)
