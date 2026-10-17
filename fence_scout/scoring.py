"""Point-based fence score (0-100). Same factors as the 'Score Key' tab in the Lead List."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

DEFAULT_SCORING = {
    "factors": {
        "Graying": {"None": 0, "Slight": 8, "Moderate": 16, "Heavy": 25},
        "Stain fade": {"None": 0, "Light": 5, "Moderate": 10, "Heavy": 15},
        "New, unsealed": {"No": 0, "Yes": 15},
        "Damage": {"None": 0, "Minor": 10, "Major": 20},
        "Run length": {"Short": 0, "Medium": 5, "Long": 10},
        "Address conf.": {"Low": 0, "Medium": 5, "High": 10},
        "Imagery age": {">24 mo": 0, "12-24 mo": 3, "<12 mo": 5},
    },
    "descriptions": {
        "Graying": "How gray the wood looks",
        "Stain fade": "How much old stain has worn off",
        "New, unsealed": "New wood never stained = protect-it sale",
        "Damage": "Broken pickets / bottom boards, leaning",
        "Run length": "Longer run = bigger ticket",
        "Address conf.": "Sure the fence belongs to this address?",
        "Imagery age": "How recent the Street View photo is",
    },
    "go_first_at": 50,
    "worth_a_knock_at": 30,
}

FACTOR_ORDER = list(DEFAULT_SCORING["factors"])


def load_scoring(path: str | Path | None) -> dict:
    if path and Path(path).exists():
        cfg = json.loads(Path(path).read_text())
        return {**DEFAULT_SCORING, **cfg}
    return DEFAULT_SCORING


def imagery_age_level(yyyymm: str, today: date | None = None) -> str:
    today = today or date.today()
    try:
        y, m = (int(x) for x in yyyymm.split("-")[:2])
    except (ValueError, AttributeError):
        return ">24 mo"
    months = (today.year - y) * 12 + (today.month - m)
    if months < 12:
        return "<12 mo"
    if months <= 24:
        return "12-24 mo"
    return ">24 mo"


def score(levels: dict[str, str], cfg: dict = DEFAULT_SCORING) -> int:
    total = sum(cfg["factors"][f].get(levels.get(f, ""), 0) for f in cfg["factors"])
    return min(100, total)


def action(points: int, cfg: dict = DEFAULT_SCORING) -> str:
    if points >= cfg["go_first_at"]:
        return "Go first"
    if points >= cfg["worth_a_knock_at"]:
        return "Worth a knock"
    return "Skip"


def service(levels: dict[str, str]) -> str:
    dmg = levels.get("Damage", "None")
    weathered = levels.get("Graying") in ("Moderate", "Heavy") or levels.get("Stain fade") in ("Moderate", "Heavy")
    if dmg == "Major":
        return "Repair / replacement check"
    if dmg == "Minor":
        return "Repair ($99), then stain" if weathered else "Repair ($99)"
    if levels.get("New, unsealed") == "Yes":
        return "Protect new fence"
    if weathered:
        return "Stain"
    if levels.get("Graying") == "Slight" or levels.get("Stain fade") == "Light":
        return "Stain later"
    return "None seen"
