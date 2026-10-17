"""Pull the alley / street network around a point from OpenStreetMap (Overpass API, free)."""
from __future__ import annotations

from dataclasses import dataclass

import requests

from .geo import LatLng

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

ROAD_FILTERS = {
    # DFW alleys are usually tagged highway=service + service=alley
    "alleys": ['["highway"="service"]["service"="alley"]'],
    "streets": ['["highway"~"^(residential|living_street)$"]'],
}
ROAD_FILTERS["both"] = ROAD_FILTERS["alleys"] + ROAD_FILTERS["streets"]


@dataclass
class Way:
    id: int
    kind: str  # "alley" or "street"
    name: str
    coords: list[LatLng]

    @property
    def label(self) -> str:
        return self.name or ("Alley" if self.kind == "alley" else "Unnamed street")


def build_query(center: LatLng, radius_m: float, roads: str) -> str:
    parts = "".join(
        f"way(around:{int(radius_m)},{center.lat},{center.lng}){f};" for f in ROAD_FILTERS[roads]
    )
    return f"[out:json][timeout:90];({parts});(._;>;);out body;"


def parse_overpass(data: dict) -> list[Way]:
    nodes = {e["id"]: LatLng(e["lat"], e["lon"]) for e in data.get("elements", []) if e["type"] == "node"}
    ways: list[Way] = []
    for e in data.get("elements", []):
        if e["type"] != "way":
            continue
        tags = e.get("tags", {})
        kind = "alley" if tags.get("service") == "alley" else "street"
        coords = [nodes[n] for n in e.get("nodes", []) if n in nodes]
        if len(coords) >= 2:
            ways.append(Way(e["id"], kind, tags.get("name", ""), coords))
    return ways


def fetch_ways(center: LatLng, radius_m: float, roads: str = "alleys", session: requests.Session | None = None) -> list[Way]:
    s = session or requests.Session()
    r = s.post(OVERPASS_URL, data={"data": build_query(center, radius_m, roads)}, timeout=120,
               headers={"User-Agent": "fence-scout/0.1 (Harbinger Fence lead research)"})
    r.raise_for_status()
    return parse_overpass(r.json())
