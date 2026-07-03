#!/usr/bin/env python3
"""
Turns data/r6prep_raw/<map>/<map>_data.json + room_labels.json (filled in
by hand after reviewing the annotated overlay images from
r6prep_extract.py) into data/strategies/<map>_defense.json in the app's
normal schema, with a real per-marker photo path on every item.

Usage: python3 scripts/r6prep_build.py <map-slug> "<Display Name>"
    e.g. python3 scripts/r6prep_build.py chalet "Chalet"
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

ROTATE_TYPE_LABEL = {"soft": "Stand", "crouch": "Crouch", "prone": "Prone", "hatch": "Hatch Rotate", "jump": "Jump"}
FLOOR_LABEL = {"base": "Basement", "1f": "1st Floor", "2f": "2nd Floor", "3f": "3rd Floor"}


def photo_path(map_slug, sc_id):
    if not sc_id:
        # A handful of r6prep markers ship with no screenshot_id at all (a
        # gap in their own data, not an extraction bug) — leave the photo
        # field blank rather than crash or fabricate a path.
        return ""
    return f"assets/site-photos/{map_slug}/{sc_id}.webp"


def clean_working_name(display_name):
    # r6prep prefixes EACH comma-separated room with its own floor token
    # ("2F Executive Lounge, 2F CEO Office") — build_data.py's floor_prefix()
    # adds its own canonical prefix on top of workingName, so strip r6prep's
    # redundant per-room tokens here or the site picker shows "2F 2F ...".
    parts = [re.sub(r"^(B|1F|2F|3F)\s+", "", p.strip()) for p in display_name.split(",")]
    return " / ".join(parts)


def dedupe_locations(*groups):
    """Ensures every location string is globally unique within a site by
    appending a counter suffix to repeats — identical room names across
    different marker categories is a real naming collision (not a physical
    one), and build_data.py's reinforce/head-hole exact-match guard can't
    tell the difference unless the strings are actually distinct."""
    seen = {}
    for group in groups:
        for entry in group:
            base = entry["location"]
            seen[base] = seen.get(base, 0) + 1
            if seen[base] > 1:
                entry["location"] = f"{base} ({seen[base]})"


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    slug, display_name = sys.argv[1], sys.argv[2]
    raw_dir = ROOT / "data" / "r6prep_raw" / slug
    # r6prep_extract.py names this file after r6prep's OWN URL slug, which
    # differs from ours for a few maps (calypso_casino/calypso,
    # club_house/clubhouse, kafe_dostoyevsky/kafe-dostoyevsky,
    # nighthaven_labs/nighthaven-labs) — glob instead of assuming the local
    # slug, so this works regardless of which slug produced the file.
    data_files = list(raw_dir.glob("*_data.json"))
    if len(data_files) != 1:
        print(f"Expected exactly one *_data.json in {raw_dir}, found {len(data_files)}: {data_files}")
        sys.exit(1)
    data = json.loads(data_files[0].read_text())
    labels = json.loads((raw_dir / "room_labels.json").read_text())

    sites_out = []
    for site_id, setup in data["setups"].items():
        site_meta = [s for s in data["map"]["sites"] if s["id"] == site_id][0]
        layer = [l for l in setup["layers"] if l["is_primary"]][0]
        room_map = labels[site_id]

        reinforcements, hatches, headHoles, rotates = [], [], [], []
        n = 0
        for item in layer.get("reinforcements", []):
            n += 1
            room = room_map[str(n)]
            orient = item.get("wall_orientation", "")
            entry = {
                "location": room if orient == "hatch" else f"{room}, {orient.capitalize()} Wall",
                "note": "",
                "timestamp": "",
                "photo": photo_path(slug, item.get("screenshot_id")),
            }
            (hatches if orient == "hatch" else reinforcements).append(entry)
        for item in layer.get("headholes", []):
            n += 1
            room = room_map[str(n)]
            headHoles.append({"location": room, "note": "", "timestamp": "", "photo": photo_path(slug, item.get("screenshot_id"))})
        for item in layer.get("footholes", []):
            n += 1
            room = room_map[str(n)]
            headHoles.append({"location": f"{room}, Foot Hole", "note": "", "timestamp": "", "photo": photo_path(slug, item.get("screenshot_id"))})
        for item in layer.get("highholes", []):
            n += 1
            room = room_map[str(n)]
            headHoles.append({"location": f"{room}, High Hole", "note": "", "timestamp": "", "photo": photo_path(slug, item.get("screenshot_id"))})
        for item in layer.get("rotations", []):
            n += 1
            room = room_map[str(n)]
            rtype = ROTATE_TYPE_LABEL.get(item["type"], item["type"].capitalize())
            rotates.append({"location": f"{room}, {rtype}", "note": "", "timestamp": "", "photo": photo_path(slug, item.get("screenshot_id"))})

        dedupe_locations(reinforcements, hatches, headHoles, rotates)

        sites_out.append(
            {
                "id": site_id,
                "workingName": clean_working_name(site_meta["display_name"]),
                "floor": FLOOR_LABEL[site_meta["floor"]],
                "callouts": sorted(set(room_map.values())),
                "reinforcements": reinforcements,
                "headHoles": headHoles,
                "rotates": rotates,
                "hatches": hatches,
                "gadgetPlacements": [],
                "operatorRecommendations": [],
                "generalTips": [],
            }
        )

    source_url = data["setups"][list(data["setups"].keys())[0]]["sources"][0]["url"]
    out = {
        "map": display_name,
        "side": "Defense",
        "source": {
            "title": f"R6 Prep — Defender Site Setups: {display_name}",
            "type": "r6prep_site_setups",
            "file": f"https://www.r6prep.com/defender/site-setups/{slug}",
            "notes": (
                "Wall/hatch/rotation/head-hole/foot-hole positions and per-marker screenshots sourced directly "
                f"from r6prep.com's structured site-setup data (r6prep's own source: {source_url}). r6prep "
                "provides no text room names or descriptions, only marker position + category + photo — room "
                "names above were inferred by the app's maintainer from each marker's visual position on the "
                "base map, cross-checked against wiki-verified callouts (data/maps/*.json). Treat room labels "
                "as best-effort; the linked photo is the authoritative reference for exact placement. No "
                "operator/loadout/utility recommendations in this source — that content is tracked separately."
            ),
        },
        "sites": sites_out,
    }
    out_path = ROOT / "data" / "strategies" / f"{slug}_defense.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
