"""Command line entry point.

    python -m fence_scout scan --address "6540 Village Springs Dr, Plano, TX 75024" --radius 300
    python -m fence_scout scan --address "..." --miles 1 --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .cache import Cache
from .export import merge, read_existing, write_workbook
from .geo import LatLng
from .google import Google
from .osm import fetch_ways
from .pipeline import plan_scan, run_scan
from .scoring import load_scoring
from .vision import Grader

MILE = 1609.34


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(prog="fence_scout", description="Scan alleys/streets for weathered fences.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="scan an area and add leads to the Excel list")
    where = s.add_mutually_exclusive_group(required=True)
    where.add_argument("--address", help='center address, e.g. "6540 Village Springs Dr, Plano, TX 75024"')
    where.add_argument("--latlng", help="center as lat,lng")
    size = s.add_mutually_exclusive_group()
    size.add_argument("--radius", type=float, default=300, help="radius in metres (default 300)")
    size.add_argument("--miles", type=float, help="radius in miles (overrides --radius)")
    s.add_argument("--roads", choices=["alleys", "streets", "both"], default="alleys",
                   help="what to drive: alleys (back fences, default), streets, or both")
    s.add_argument("--step", type=float, default=12, help="metres between stops (default 12)")
    s.add_argument("--max-images", type=int, default=300, help="stop before paying for more than this many new images")
    s.add_argument("--yes", action="store_true", help="don't ask before spending")
    s.add_argument("--dry-run", action="store_true", help="count roads/panoramas and estimate cost only (no paid calls except 1 geocode)")
    s.add_argument("--out", default="Fence_Scout_Lead_List.xlsx", help="Excel file to add leads to")
    s.add_argument("--area-name", default="", help='label for the Area / Alley column, e.g. "Kings Ridge alleys"')
    s.add_argument("--scoring", default="scoring.json", help="optional scoring override file")
    s.add_argument("--print-json", action="store_true",
                   help="also print each lead as a 'FENCE_LEAD {json}' log line (used when running on Railway)")
    a = p.parse_args(argv)

    cfg = load_scoring(a.scoring)
    radius = a.miles * MILE if a.miles else a.radius
    cache = Cache(os.getenv("FENCE_SCOUT_CACHE", ".cache/fence_scout.db"))
    google = Google(os.getenv("GOOGLE_MAPS_API_KEY", ""), cache)
    img_price = float(os.getenv("SV_PRICE_PER_1000", "7.00"))
    ai_price = float(os.getenv("AI_PRICE_PER_IMAGE", "0.006"))

    if a.address:
        center, label = google.geocode(a.address)
    else:
        lat, lng = (float(x) for x in a.latlng.split(","))
        center, label = LatLng(lat, lng), a.latlng
    print(f"Center: {label}  ({center})  radius {radius:.0f} m, roads={a.roads}")

    print("Finding roads (OpenStreetMap)...")
    ways = fetch_ways(center, radius, a.roads)
    if not ways:
        print("No matching roads found. Try --roads both or a bigger radius.")
        return 1
    print("Finding Street View panoramas (free metadata lookups)...")
    plan = plan_scan(center, ways, radius, a.step, google)
    new = plan.new_views(cache)
    est = len(new) * (img_price / 1000 + ai_price)
    print(f"New views to pay for: {len(new)} (already graded: {len(plan.views) - len(new)})")
    print(f"Estimated cost: ~${est:.2f}  (images ${img_price}/1000 after Google's 10,000 free/month + AI ~${ai_price}/image)")
    if a.dry_run:
        return 0
    if len(new) > a.max_images:
        print(f"That's more than --max-images {a.max_images}. Shrink the radius or raise --max-images.")
        return 2
    if new and not a.yes:
        if input("Proceed? [y/N] ").strip().lower() != "y":
            return 0

    grader = Grader(os.getenv("ANTHROPIC_API_KEY", ""), os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"), cache)
    area = a.area_name or f"Scan near {label.split(',')[0]}"
    print("Grading fences...")
    leads = run_scan(plan, google, grader, cfg, area)
    if a.print_json:
        import json
        for r in leads:
            print("FENCE_LEAD " + json.dumps(r), flush=True)

    out = Path(a.out)
    existing = read_existing(out)
    rows, added = merge(existing, leads)
    try:
        write_workbook(rows, out, cfg)
    except PermissionError:
        alt = out.with_name(out.stem + "_new.xlsx")
        write_workbook(rows, alt, cfg)
        print(f"{out} is open in Excel - saved to {alt} instead.")
        out = alt
    go = sum(1 for r in leads if r["_action"] == "Go first")
    knock = sum(1 for r in leads if r["_action"] == "Worth a knock")
    print(f"\nDone. {len(leads)} wood fences found -> {go} Go first, {knock} Worth a knock.")
    print(f"{added} new addresses added to {out} (now {len(rows)} total).")
    print(f"Paid calls this run: {google.paid_images} images, {grader.calls} AI grades, {google.paid_geocodes} geocodes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
