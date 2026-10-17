"""Small geometry helpers (no external deps)."""
from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_R = 6_371_000.0


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float

    def __str__(self) -> str:
        return f"{self.lat:.7f},{self.lng:.7f}"


def haversine_m(a: LatLng, b: LatLng) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = p2 - p1
    dl = math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


def bearing_deg(a: LatLng, b: LatLng) -> float:
    """Initial compass bearing a -> b, 0..360 (0 = north, 90 = east)."""
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dl = math.radians(b.lng - a.lng)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def offset(p: LatLng, heading: float, dist_m: float) -> LatLng:
    """Point dist_m metres from p along compass heading."""
    d = dist_m / EARTH_R
    h = math.radians(heading)
    lat1, lng1 = math.radians(p.lat), math.radians(p.lng)
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(h))
    lng2 = lng1 + math.atan2(
        math.sin(h) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2)
    )
    return LatLng(math.degrees(lat2), (math.degrees(lng2) + 540) % 360 - 180)


def norm_heading(h: float) -> float:
    return h % 360


@dataclass(frozen=True)
class SamplePoint:
    point: LatLng
    road_bearing: float  # direction of travel along the road
    way_id: int
    way_label: str


def sample_polyline(coords: list[LatLng], step_m: float, way_id: int = 0, label: str = "") -> list[SamplePoint]:
    """Points every step_m metres along a polyline, each with the local road bearing."""
    out: list[SamplePoint] = []
    if len(coords) < 2:
        return out
    carry = 0.0  # distance into current segment where next sample falls
    for a, b in zip(coords, coords[1:]):
        seg = haversine_m(a, b)
        if seg == 0:
            continue
        brg = bearing_deg(a, b)
        d = carry
        while d <= seg:
            out.append(SamplePoint(offset(a, brg, d), brg, way_id, label))
            d += step_m
        carry = d - seg
    return out


def within_radius(p: LatLng, center: LatLng, radius_m: float) -> bool:
    return haversine_m(p, center) <= radius_m
