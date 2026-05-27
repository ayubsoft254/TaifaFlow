from __future__ import annotations

import heapq
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class RoadEdge:
    source: str
    destination: str
    segment_id: str
    base_cost: float


class RouteOptimizer:
    """Computes a least-cost route weighted by live traffic severity."""

    SEVERITY_MULTIPLIER = {
        "low": 1.0,
        "medium": 1.3,
        "high": 1.9,
        "critical": 4.0,
    }

    def __init__(self) -> None:
        # Baseline road graph for initial dashboard routing.
        self.edges = [
            RoadEdge("westlands", "cbd", "seg_westlands_cbd", 4.0),
            RoadEdge("westlands", "upper_hill", "seg_westlands_upper_hill", 6.0),
            RoadEdge("westlands", "kileleshwa", "seg_westlands_kileleshwa", 3.0),
            RoadEdge("kileleshwa", "upper_hill", "seg_kileleshwa_upper_hill", 5.0),
            RoadEdge("cbd", "upper_hill", "seg_cbd_upper_hill", 2.5),
            RoadEdge("cbd", "embakasi", "seg_cbd_embakasi", 11.0),
            RoadEdge("upper_hill", "embakasi", "seg_upper_hill_embakasi", 9.0),
            RoadEdge("embakasi", "kasarani", "seg_embakasi_kasarani", 8.0),
            RoadEdge("cbd", "kasarani", "seg_cbd_kasarani", 10.0),
            RoadEdge("kileleshwa", "cbd", "seg_kileleshwa_cbd", 4.2),
        ]

    def available_points(self) -> list[str]:
        points = {edge.source for edge in self.edges} | {edge.destination for edge in self.edges}
        return sorted(points)

    async def find_optimal_route(self, redis_client: Redis, origin: str, destination: str) -> dict[str, object]:
        origin_norm = origin.strip().lower()
        destination_norm = destination.strip().lower()
        points = set(self.available_points())

        if origin_norm not in points or destination_norm not in points:
            return {
                "found": False,
                "error": "Unknown route points selected.",
                "path": [],
                "cost": 0.0,
                "segment_details": [],
            }

        if origin_norm == destination_norm:
            return {
                "found": True,
                "path": [origin_norm],
                "cost": 0.0,
                "segment_details": [],
            }

        adjacency: dict[str, list[RoadEdge]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.source, []).append(edge)
            adjacency.setdefault(edge.destination, []).append(
                RoadEdge(edge.destination, edge.source, edge.segment_id, edge.base_cost)
            )

        segment_severity = await self._segment_severity_map(redis_client)
        return self._dijkstra(adjacency, origin_norm, destination_norm, segment_severity)

    async def _segment_severity_map(self, redis_client: Redis) -> dict[str, str]:
        severities: dict[str, str] = {}
        try:
            for edge in self.edges:
                data = await redis_client.hgetall(f"segment:{edge.segment_id}")
                if not data:
                    continue

                severity = str(data.get("severity", "low")).lower()
                if severity in self.SEVERITY_MULTIPLIER:
                    severities[edge.segment_id] = severity
        except Exception:
            # Degrade to baseline low-severity weights when Redis is unavailable.
            return {}

        return severities

    def _dijkstra(
        self,
        adjacency: dict[str, list[RoadEdge]],
        origin: str,
        destination: str,
        segment_severity: dict[str, str],
    ) -> dict[str, object]:
        heap: list[tuple[float, str]] = [(0.0, origin)]
        dist: dict[str, float] = {origin: 0.0}
        prev: dict[str, tuple[str, RoadEdge]] = {}

        while heap:
            current_cost, node = heapq.heappop(heap)
            if node == destination:
                break
            if current_cost > dist.get(node, float("inf")):
                continue

            for edge in adjacency.get(node, []):
                severity = segment_severity.get(edge.segment_id, "low")
                multiplier = self.SEVERITY_MULTIPLIER.get(severity, 1.0)
                edge_cost = edge.base_cost * multiplier
                new_cost = current_cost + edge_cost

                if new_cost < dist.get(edge.destination, float("inf")):
                    dist[edge.destination] = new_cost
                    prev[edge.destination] = (node, edge)
                    heapq.heappush(heap, (new_cost, edge.destination))

        if destination not in dist:
            return {
                "found": False,
                "error": "No route found between the selected points.",
                "path": [],
                "cost": 0.0,
                "segment_details": [],
            }

        path_nodes: list[str] = []
        segment_details: list[dict[str, object]] = []
        current = destination

        while current != origin:
            path_nodes.append(current)
            parent, edge = prev[current]
            severity = segment_severity.get(edge.segment_id, "low")
            multiplier = self.SEVERITY_MULTIPLIER.get(severity, 1.0)
            segment_details.append(
                {
                    "segment_id": edge.segment_id,
                    "from": edge.source,
                    "to": edge.destination,
                    "severity": severity,
                    "cost": round(edge.base_cost * multiplier, 2),
                }
            )
            current = parent

        path_nodes.append(origin)
        path_nodes.reverse()
        segment_details.reverse()

        return {
            "found": True,
            "path": path_nodes,
            "cost": round(dist[destination], 2),
            "segment_details": segment_details,
        }