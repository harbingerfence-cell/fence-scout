"""Run a scan from environment variables (for Railway or any cloud runner).

    SCAN_ADDRESS    center address (required)
    SCAN_RADIUS     metres, default 250
    SCAN_ROADS      alleys | streets | both (default alleys)
    SCAN_MAX_IMAGES default 300
    SCAN_AREA_NAME  label for the Area / Alley column
    SCAN_DRY_RUN    "1" (default) = estimate only, "0" = really scan and grade

Leads are printed as 'FENCE_LEAD {json}' lines so they can be read back from the logs.
"""
from __future__ import annotations

import os
import sys

from .cli import main


def build_argv(env: dict) -> list[str]:
    addr = env.get("SCAN_ADDRESS", "").strip()
    if not addr:
        raise SystemExit("Set SCAN_ADDRESS")
    argv = ["scan", "--address", addr,
            "--radius", env.get("SCAN_RADIUS", "250"),
            "--roads", env.get("SCAN_ROADS", "alleys"),
            "--max-images", env.get("SCAN_MAX_IMAGES", "300"),
            "--out", "/tmp/Fence_Scout_Lead_List.xlsx",
            "--yes", "--print-json"]
    if env.get("SCAN_AREA_NAME"):
        argv += ["--area-name", env["SCAN_AREA_NAME"]]
    if env.get("SCAN_DRY_RUN", "1") != "0":
        argv.append("--dry-run")
    return argv


if __name__ == "__main__":
    print("FENCE_JOB start", flush=True)
    code = main(build_argv(dict(os.environ)))
    print(f"FENCE_JOB done exit={code}", flush=True)
    sys.exit(code)
