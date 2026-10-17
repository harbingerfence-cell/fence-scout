# Fence Scout

Drives alleys (or streets) in Google Street View automatically, has Claude grade each fence,
matches it to an address, scores it 0–100 and adds it to a running Excel **Lead List** for Harbinger Fence.

## How it works

1. **Roads**: pulls every alley (and/or residential street) within your radius from OpenStreetMap (free).
2. **Stops**: drops a stop every 12 m along each road.
3. **Panoramas**: finds the Street View panorama at each stop and its capture date (free metadata call).
4. **Photos**: grabs one photo looking left and one looking right (paid; 10,000 free per month).
5. **Grading**: Claude grades each photo: graying, stain fade, new/unsealed, damage and run length.
6. **Address**: reverse-geocodes a point inside the lot the camera faces. Confidence goes up if Claude can read a house number.
7. **Lead List**: scores each fence with the same points as the **Score Key** tab and adds new addresses to the Excel file.
   Your Y/N answers and notes on existing rows are never overwritten.

## Setup (Windows, one time)

```powershell
cd fence-scout
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env        # paste GOOGLE_MAPS_API_KEY and ANTHROPIC_API_KEY
```

The Google key needs **Street View Static API** and **Geocoding API** enabled in Google Cloud Console.

## Run

Always do a dry run first. It finds the roads and panoramas and prints the cost, with no paid image or AI calls:

```powershell
python -m fence_scout scan --address "6540 Village Springs Dr, Plano, TX 75024" --radius 250 --dry-run
```

Then run it for real:

```powershell
python -m fence_scout scan --address "6540 Village Springs Dr, Plano, TX 75024" --radius 250 --area-name "Kings Ridge alleys"
```

| Option | Meaning |
|---|---|
| `--radius 300` / `--miles 1` | Size of the area |
| `--roads alleys` (default) / `streets` / `both` | What to drive. Alleys show back fences best |
| `--max-images 300` | Hard stop before spending on more photos |
| `--out My_List.xlsx` | Which Excel file to add to (default `Fence_Scout_Lead_List.xlsx`) |
| `--yes` | Skip the "Proceed?" prompt |

Re-running the same area costs almost nothing, because each photo's grade is cached in `.cache/`.

## Rough cost

About 2 photos per 24 m of alley, so a typical 200 m alley is around 16 photos.

- **Photos:** Google gives 10,000 free per month, then $7 per 1,000.
- **AI grading:** about $0.006 per photo with Sonnet. Set `CLAUDE_MODEL=claude-haiku-5-5` in `.env` for much cheaper grading.

## Limits to know

- **Old imagery:** Street View photos can be 1–3 years old. The photo date is shown in "What to check" and lowers the score.
- **Unmapped alleys:** some alleys aren't tagged in OpenStreetMap. If a known alley is skipped, try `--roads both`.
- **Address matching:** this is the weak spot, especially on corner lots. Rows marked Low say "Confirm which house owns this fence"; check those before mailing.
- **Image storage:** Google's terms restrict storing Street View images, so the tool doesn't save them. It keeps only the AI's grades.

## Tests

```powershell
python -m pytest -q
```
