"""Google Maps Platform calls: geocoding, Street View metadata (free) and Street View images (paid)."""
from __future__ import annotations

import base64
from dataclasses import dataclass

import requests

from .cache import Cache
from .geo import LatLng

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
SV_META_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
SV_IMG_URL = "https://maps.googleapis.com/maps/api/streetview"


@dataclass
class Pano:
    pano_id: str
    location: LatLng
    date: str  # "YYYY-MM" (may be "")


class GoogleError(RuntimeError):
    pass


class Google:
    def __init__(self, api_key: str, cache: Cache, session: requests.Session | None = None):
        if not api_key:
            raise GoogleError("GOOGLE_MAPS_API_KEY is missing - add it to your .env file")
        self.key = api_key
        self.cache = cache
        self.s = session or requests.Session()
        self.paid_images = 0
        self.paid_geocodes = 0

    def _get(self, url: str, params: dict) -> requests.Response:
        r = self.s.get(url, params={**params, "key": self.key}, timeout=30)
        r.raise_for_status()
        return r

    # ---------- geocoding ----------
    def geocode(self, address: str) -> tuple[LatLng, str]:
        hit = self.cache.get("geocode", address.lower())
        if hit is None:
            data = self._get(GEOCODE_URL, {"address": address}).json()
            self.paid_geocodes += 1
            if data.get("status") != "OK":
                raise GoogleError(f"Could not find address '{address}': {data.get('status')} {data.get('error_message', '')}")
            res = data["results"][0]
            hit = {"lat": res["geometry"]["location"]["lat"], "lng": res["geometry"]["location"]["lng"],
                   "formatted": res["formatted_address"]}
            self.cache.set("geocode", address.lower(), hit)
        return LatLng(hit["lat"], hit["lng"]), hit["formatted"]

    def reverse_geocode(self, p: LatLng) -> dict | None:
        """Nearest street address to a point. Returns {address, location_type} or None."""
        key = f"{p.lat:.6f},{p.lng:.6f}"
        hit = self.cache.get("revgeo", key)
        if hit is None:
            data = self._get(GEOCODE_URL, {"latlng": key, "result_type": "street_address|premise"}).json()
            self.paid_geocodes += 1
            if data.get("status") != "OK" or not data.get("results"):
                hit = {}
            else:
                res = data["results"][0]
                hit = {"address": clean_address(res["formatted_address"]),
                       "location_type": res["geometry"].get("location_type", ""),
                       "lat": res["geometry"]["location"]["lat"], "lng": res["geometry"]["location"]["lng"]}
            self.cache.set("revgeo", key, hit)
        return hit or None

    # ---------- street view ----------
    def pano_near(self, p: LatLng, radius_m: int = 10) -> Pano | None:
        """Metadata lookup (no charge). None if no outdoor panorama within radius."""
        key = f"{p.lat:.6f},{p.lng:.6f},{radius_m}"
        hit = self.cache.get("svmeta", key)
        if hit is None:
            data = self._get(SV_META_URL, {"location": f"{p.lat},{p.lng}", "radius": radius_m, "source": "outdoor"}).json()
            hit = data if data.get("status") == "OK" else {}
            self.cache.set("svmeta", key, hit)
        if not hit:
            return None
        return Pano(hit["pano_id"], LatLng(hit["location"]["lat"], hit["location"]["lng"]), hit.get("date", ""))

    def image_b64(self, pano_id: str, heading: float, size: str = "640x640", fov: int = 90, pitch: int = 0) -> str:
        """Paid call. Images are NOT stored (Google's terms restrict caching imagery);
        the AI's verdict on each pano+heading is cached instead, so reruns skip this call."""
        r = self._get(SV_IMG_URL, {"pano": pano_id, "heading": f"{heading:.1f}", "size": size,
                                   "fov": fov, "pitch": pitch, "source": "outdoor"})
        self.paid_images += 1
        return base64.b64encode(r.content).decode()


def clean_address(a: str) -> str:
    return a.removesuffix(", USA").strip()


def street_view_link(p: LatLng, heading: float) -> str:
    """Public Maps URL that opens Street View at p facing heading (no API key)."""
    return (f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={p.lat:.7f},{p.lng:.7f}"
            f"&heading={heading:.0f}&pitch=0&fov=90")


def map_link(address: str) -> str:
    from urllib.parse import quote_plus
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}"
