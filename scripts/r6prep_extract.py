#!/usr/bin/env python3
"""
Pulls a map's defender site-setup data straight out of r6prep.com's page
payload (Next.js embeds it as structured JSON in the initial HTML — no
scraping/clicking required) and downloads every marker's real screenshot.

r6prep has no text descriptions or room names, only marker position +
category + a real in-game photo. Room names must still be assigned by hand
(see data/r6prep_raw/<map>/room_labels.json) by looking at the annotated
overlay this script produces.

Usage:
    python3 scripts/r6prep_extract.py <r6prep-slug> [local-slug]
    # e.g. python3 scripts/r6prep_extract.py chalet
    # e.g. python3 scripts/r6prep_extract.py club_house clubhouse
    #      (r6prep's URL slug differs from ours for a few maps —
    #      calypso_casino/calypso, club_house/clubhouse,
    #      kafe_dostoyevsky/kafe-dostoyevsky, nighthaven_labs/nighthaven-labs.
    #      Pass local-slug to write output under OUR naming convention,
    #      matching data/maps/<local-slug>.json, while still fetching from
    #      r6prep's URL. Defaults to the same as r6prep-slug.)

Produces:
    data/r6prep_raw/<local-slug>/<r6prep-slug>_data.json — raw r6prep payload
    data/r6prep_raw/<local-slug>/<site>_annotated.png    — base map with
                                                             numbered markers,
                                                             for room-naming
    assets/site-photos/<local-slug>/sc_*.webp — every real per-marker photo

After room_labels.json is filled in by hand, use r6prep_build.py to turn
this into data/strategies/<local-slug>_defense.json.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def extract_map_data(html):
    matches = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL)
    for m in matches:
        chunk = m.encode().decode("unicode_escape")
        idx = chunk.find('{"map":{"id"')
        if idx == -1:
            continue
        depth = 0
        start = idx
        for i, ch in enumerate(chunk[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(chunk[start : i + 1])
    return None


def main():
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(1)
    slug = sys.argv[1]
    local_slug = sys.argv[2] if len(sys.argv) == 3 else slug
    out_dir = ROOT / "data" / "r6prep_raw" / local_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    photos_dir = ROOT / "assets" / "site-photos" / local_slug
    photos_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://www.r6prep.com/defender/site-setups/{slug}"
    html_path = out_dir / f"{slug}_page.html"
    subprocess.run(["curl", "-s", "-o", str(html_path), url], check=True)
    data = extract_map_data(html_path.read_text())
    if not data:
        print(f"Could not find embedded map data for {slug} — check the URL/slug.")
        sys.exit(1)

    data_path = out_dir / f"{slug}_data.json"
    data_path.write_text(json.dumps(data, indent=2))
    print(f"wrote {data_path}")

    # Download base floor images + every unique marker screenshot.
    needed = set()
    for site_id, setup in data["setups"].items():
        layer = [l for l in setup["layers"] if l["is_primary"]][0]
        for kind in ("reinforcements", "headholes", "footholes", "highholes"):
            for item in layer.get(kind, []):
                if item.get("screenshot_id"):
                    needed.add((site_id, item["screenshot_id"]))
        for item in layer.get("rotations", []):
            if item.get("screenshot_id"):
                needed.add((site_id, item["screenshot_id"]))

    for site in data["map"]["sites"]:
        img_key = site["image_key"]
        base_path = out_dir / f"{img_key.split('/')[-1]}.webp"
        if not base_path.exists():
            subprocess.run(
                ["curl", "-s", "-o", str(base_path), f"https://www.r6prep.com/maps/{img_key}.webp"],
                check=True,
            )

    for site_id, sc_id in needed:
        img_key = [s for s in data["map"]["sites"] if s["id"] == site_id][0]["image_key"]
        out_path = photos_dir / f"{sc_id}.webp"
        if out_path.exists():
            continue
        subprocess.run(
            ["curl", "-s", "-o", str(out_path), f"https://www.r6prep.com/screenshots/{img_key}/{sc_id}.webp"],
            check=True,
        )
    print(f"{len(needed)} unique marker photos in {photos_dir}")

    # Annotate each site's base image with numbered markers so room names
    # can be assigned by eye in one pass instead of clicking through the UI.
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow not installed — skipping annotated overlays (pip install Pillow)")
        return

    COLORS = {
        "reinforcements": (80, 140, 255),
        "headholes": (60, 200, 120),
        "footholes": (230, 80, 140),
        "highholes": (170, 100, 230),
        "rotations": (255, 180, 60),
        "bombs": (240, 210, 40),
    }
    labels_template = {}
    for site_id, setup in data["setups"].items():
        site_info = [s for s in data["map"]["sites"] if s["id"] == site_id][0]
        img_path = out_dir / f"{site_info['image_key'].split('/')[-1]}.webp"
        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        draw = ImageDraw.Draw(img)
        primary_layer = [l for l in setup["layers"] if l["is_primary"]][0]
        n = 0
        site_labels = {}
        for kind in ("reinforcements", "headholes", "footholes", "highholes"):
            for item in primary_layer.get(kind, []):
                n += 1
                x, y = item["x"] * w, item["y"] * h
                draw.ellipse([x - 10, y - 10, x + 10, y + 10], fill=COLORS[kind], outline=(0, 0, 0))
                draw.text((x + 12, y - 8), str(n), fill=(255, 255, 255))
                site_labels[str(n)] = "TODO"
        for item in primary_layer.get("rotations", []):
            n += 1
            p0, p1 = item["path"][0], item["path"][-1]
            x, y = (p0["x"] + p1["x"]) / 2 * w, (p0["y"] + p1["y"]) / 2 * h
            draw.ellipse([x - 10, y - 10, x + 10, y + 10], fill=COLORS["rotations"], outline=(0, 0, 0))
            draw.text((x + 12, y - 8), str(n), fill=(255, 255, 255))
            site_labels[str(n)] = "TODO"
        for item in primary_layer.get("bombs", []):
            n += 1
            x, y = item["x"] * w, item["y"] * h
            draw.ellipse([x - 10, y - 10, x + 10, y + 10], fill=COLORS["bombs"], outline=(0, 0, 0))
            draw.text((x + 12, y - 8), str(n), fill=(255, 255, 255))
        out_path = out_dir / f"{site_id}_annotated.png"
        img.save(out_path)
        print(f"{site_id}: {n} markers -> {out_path}")
        labels_template[site_id] = site_labels

    labels_path = out_dir / "room_labels.json"
    if not labels_path.exists():
        labels_path.write_text(json.dumps(labels_template, indent=2))
        print(f"wrote template {labels_path} — fill in real room names by viewing the annotated PNGs")


if __name__ == "__main__":
    main()
