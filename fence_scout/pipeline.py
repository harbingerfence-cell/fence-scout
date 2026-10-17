"""The scan: roads -> sample points -> panoramas -> AI grading -> address match -> lead rows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from .geo import LatLng, SamplePoint, bearing_deg, haversine_m, norm_heading, offset, sample_polyline, within_radius
from .google import Pano, street_view_link
from .scoring import action, imagery_age_level, score, service

COMPASS = ["North", "East", "South", "West"]


def compass(heading: float) -> str:
    return COMPASS[int(((heading % 360) + 45) // 90) % 4]


@dataclass
class View:
    pano: Pano
    heading: float
    road_label: str
    road_kind: str

    @property
    def key(self) -> str:
        return f"{self.pano.pano_id}|{self.heading:.0f}"


@dataclass
class ScanPlan:
    center: LatLng
    views: list[View] = field(default_factory=list)
    roads: int = 0
    samples: int = 0
    panos: int = 0

    def new_views(self, grader_cache) -> list[View]:
        return [v for v in self.views if grader_cache.get("vision", v.key) is None]


def plan_scan(center: LatLng, ways, radius_m: float, step_m: float, google, log: Callable = print) -> ScanPlan:
    plan = ScanPlan(center, roads=len(ways))
    seen_panos: set[str] = set()
    for w in ways:
        pts: list[SamplePoint] = [p for p in sample_polyline(w.coords, step_m, w.id, w.label)
                                  if within_radius(p.point, center, radius_m)]
        plan.samples += len(pts)
        for sp in pts:
            pano = google.pano_near(sp.point, radius_m=max(6, int(step_m * 0.6)))
            if pano is None or pano.pano_id in seen_panos:
                continue
            # pano must sit on THIS road (alley panos can snap to the cross street at the ends)
            if haversine_m(pano.location, sp.point) > step_m:
                continue
            seen_panos.add(pano.pano_id)
            for side in (-90, 90):
                plan.views.append(View(pano, norm_heading(sp.road_bearing + side), w.label, w.kind))
    plan.panos = len(seen_panos)
    log(f"  {plan.roads} roads, {plan.samples} sample points, {plan.panos} panoramas, {len(plan.views)} views")
    return plan


def match_address(google, view: View, house_number: str | None, lot_depth_m: float) -> tuple[str | None, str]:
    """Reverse-geocode a point inside the lot the camera is facing. Returns (address, confidence)."""
    target = offset(view.pano.location, view.heading, lot_depth_m)
    res = google.reverse_geocode(target)
    if not res:
        return None, "Low"
    addr = res["address"]
    if house_number and addr.split(" ")[0] == house_number.strip():
        return addr, "High"
    # address point should be on the side the camera faces
    hit = LatLng(res["lat"], res["lng"])
    off_axis = abs((bearing_deg(view.pano.location, hit) - view.heading + 180) % 360 - 180)
    if off_axis > 60:
        return addr, "Low"
    return addr, "Medium" if res.get("location_type") == "ROOFTOP" else "Low"


def what_to_check(levels: dict, notes: str) -> str:
    bits = []
    if levels["Address conf."] == "Low":
        bits.append("Confirm which house owns this fence")
    if levels["Damage"] != "None":
        bits.append("Damage still there?")
    elif levels["Graying"] in ("Moderate", "Heavy") or levels["Stain fade"] in ("Moderate", "Heavy"):
        bits.append("Still weathered or already stained?")
    elif levels["New, unsealed"] == "Yes":
        bits.append("Still unsealed?")
    text = "; ".join(bits)
    return f"{notes.rstrip('.')}. {text}".strip(". ") if notes else text


def run_scan(plan: ScanPlan, google, grader, cfg: dict, area_name: str, lot_depth_m: float = 25,
             min_confidence: float = 0.4, log: Callable = print, today: date | None = None) -> list[dict]:
    today = today or date.today()
    best: dict[str, dict] = {}
    n = len(plan.views)
    for i, v in enumerate(plan.views, 1):
        verdict = grader.cached(v.key)
        if verdict is None:
            img = google.image_b64(v.pano.pano_id, v.heading)
            verdict = grader.grade(v.key, img)
        if i % 10 == 0 or i == n:
            log(f"  graded {i}/{n} views")
        if not verdict.is_wood_fence or verdict.confidence < min_confidence:
            continue
        addr, conf = match_address(google, v, verdict.house_number, lot_depth_m)
        if not addr:
            continue
        levels = {**verdict.levels(), "Address conf.": conf, "Imagery age": imagery_age_level(v.pano.date, today)}
        pts = score(levels, cfg)
        area = area_name or (f"Alley near {v.road_label}" if v.road_kind == "alley" and v.road_label != "Alley"
                             else v.road_label)
        row = {
            "address": addr,
            "link": street_view_link(v.pano.location, v.heading),
            **levels,
            "Service": service(levels),
            "What to check": f"[Photo {v.pano.date or 'date ?'}] " + what_to_check(levels, verdict.notes),
            "Side": compass(v.heading),
            "Area / Alley": area,
            "Date scouted": today.isoformat(),
            "_score": pts,
            "_action": action(pts, cfg),
            "_imagery_date": v.pano.date,
        }
        key = addr.lower()
        # same house seen from several panoramas: keep the strongest view
        if key not in best or pts > best[key]["_score"]:
            best[key] = row
    return sorted(best.values(), key=lambda r: -r["_score"])
