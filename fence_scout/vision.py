"""Ask Claude to grade one Street View image of a fence."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

PROMPT = """You are inspecting a Google Street View photo for a residential fence-staining and repair company in Texas.
The camera is in a street or alley looking straight at ONE side (the property on that side).

Grade only the fence that belongs to the property directly in front of the camera.
Report what you can SEE - do not guess maintenance history. If no fence is clearly visible, say so.

Return ONLY a JSON object with exactly these keys:
{
  "fence_visible": "yes" | "partial" | "no",
  "material": "wood" | "metal" | "vinyl" | "masonry" | "other" | "unknown",
  "graying": "None" | "Slight" | "Moderate" | "Heavy",        // silver/gray weathered wood
  "stain_fade": "None" | "Light" | "Moderate" | "Heavy",       // old stain worn or blotchy
  "new_unsealed": "Yes" | "No",                                 // bright new wood with no stain
  "damage": "None" | "Minor" | "Major",                         // Minor: a few broken/missing pickets or bottom boards. Major: leaning sections, many boards, fallen
  "run_length": "Short" | "Medium" | "Long",                    // visible length of this property's fence
  "house_number": string or null,                               // only if clearly readable (garage, mailbox)
  "notes": string,                                              // <= 20 words, what you saw
  "confidence": number                                          // 0-1, how sure you are about the condition grades
}
Rules: a freshly stained fence (rich even color) is graying None and stain_fade None.
Shadows and sun glare are not graying. Metal/vinyl/masonry fences: set graying/stain_fade None, new_unsealed No."""


@dataclass
class Verdict:
    fence_visible: str = "no"
    material: str = "unknown"
    graying: str = "None"
    stain_fade: str = "None"
    new_unsealed: str = "No"
    damage: str = "None"
    run_length: str = "Short"
    house_number: str | None = None
    notes: str = ""
    confidence: float = 0.0
    raw: dict = field(default_factory=dict)

    @property
    def is_wood_fence(self) -> bool:
        return self.fence_visible in ("yes", "partial") and self.material == "wood"

    def levels(self) -> dict[str, str]:
        return {"Graying": self.graying, "Stain fade": self.stain_fade, "New, unsealed": self.new_unsealed,
                "Damage": self.damage, "Run length": self.run_length}


ALLOWED = {
    "fence_visible": {"yes", "partial", "no"},
    "material": {"wood", "metal", "vinyl", "masonry", "other", "unknown"},
    "graying": {"None", "Slight", "Moderate", "Heavy"},
    "stain_fade": {"None", "Light", "Moderate", "Heavy"},
    "new_unsealed": {"Yes", "No"},
    "damage": {"None", "Minor", "Major"},
    "run_length": {"Short", "Medium", "Long"},
}


def parse_verdict(text: str) -> Verdict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return Verdict(notes="unparseable model reply")
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return Verdict(notes="unparseable model reply")
    v = Verdict(raw=d)
    for k, allowed in ALLOWED.items():
        val = d.get(k)
        if isinstance(val, str):
            # tolerate case differences
            match = next((a for a in allowed if a.lower() == val.strip().lower()), None)
            if match:
                setattr(v, k, match)
    hn = d.get("house_number")
    v.house_number = str(hn).strip() if hn not in (None, "", "null") else None
    v.notes = str(d.get("notes", ""))[:200]
    try:
        v.confidence = max(0.0, min(1.0, float(d.get("confidence", 0))))
    except (TypeError, ValueError):
        v.confidence = 0.0
    return v


class Grader:
    def __init__(self, api_key: str, model: str, cache):
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is missing - add it to your .env file")
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.cache = cache
        self.calls = 0

    def cached(self, key: str) -> Verdict | None:
        hit = self.cache.get("vision", key)
        return parse_verdict(json.dumps(hit)) if hit is not None else None

    def grade(self, key: str, image_b64: str) -> Verdict:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
                {"type": "text", "text": PROMPT},
            ]}],
        )
        self.calls += 1
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        v = parse_verdict(text)
        self.cache.set("vision", key, v.raw or {"fence_visible": "no", "notes": v.notes})
        return v
