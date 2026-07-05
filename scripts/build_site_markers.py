#!/usr/bin/env python3
"""
Builds data/site_markers.json + downloads the r6prep 3D site base images, so
the app can show r6prep's own site-setup view (the angled 3D render with
reinforcement / rotation / head-hole / foot-hole / high-hole / bomb markers
laid on top) as the main map instead of the flat top-down blueprint.

Everything comes from the r6prep payloads we already extracted
(data/r6prep_raw/<map>/*_data.json): each site's primary layer carries every
marker's fractional x/y (0-1) position, rotation paths, and bomb labels, plus
the site's base image_key. This just pulls the base image and flattens the
marker geometry into one client-friendly JSON keyed by r6prep's globally
unique site id (e.g. "bank_2f"), which matches the "id" field on every site
in data/strategies/*.json — so build_data.py can attach it by site id.

Output:
    data/site_markers.json
    assets/site-maps/<map-slug>/<image-key-basename>.webp

Usage: python3 scripts/build_site_markers.py
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "r6prep_raw"
IMG_DIR = ROOT / "assets" / "site-maps"

ROT_LETTER = {"soft": "S", "crouch": "C", "prone": "P", "hatch": "H", "jump": "J"}


def main():
    out = {}
    for map_dir in sorted(RAW.iterdir()):
        if not map_dir.is_dir():
            continue
        slug = map_dir.name
        data_files = list(map_dir.glob("*_data.json"))
        if not data_files:
            continue
        data = json.loads(data_files[0].read_text())
        site_img = {s["id"]: s["image_key"] for s in data["map"]["sites"]}
        dest = IMG_DIR / slug
        dest.mkdir(parents=True, exist_ok=True)

        for site_id, setup in data["setups"].items():
            layer = [l for l in setup["layers"] if l["is_primary"]][0]
            image_key = site_img[site_id]
            base = image_key.split("/")[-1]
            img_path = dest / f"{base}.webp"
            if not img_path.exists():
                subprocess.run(
                    ["curl", "-sf", "-o", str(img_path),
                     f"https://www.r6prep.com/maps/{image_key}.webp"],
                    check=True,
                )

            def pts(kind):
                return [{"x": round(i["x"], 4), "y": round(i["y"], 4)}
                        for i in layer.get(kind, []) if "x" in i]

            rotations = []
            for r in layer.get("rotations", []):
                path = r.get("path") or []
                if not path:
                    continue
                rotations.append({
                    "x": round(path[0]["x"], 4), "y": round(path[0]["y"], 4),
                    "tx": round(path[-1]["x"], 4), "ty": round(path[-1]["y"], 4),
                    "t": ROT_LETTER.get(r.get("type", ""), "?"),
                })

            out[site_id] = {
                "image": f"assets/site-maps/{slug}/{base}.webp",
                "reinforcements": pts("reinforcements"),
                "headholes": pts("headholes"),
                "footholes": pts("footholes"),
                "highholes": pts("highholes"),
                "rotations": rotations,
                "bombs": [{"x": round(b["x"], 4), "y": round(b["y"], 4),
                           "label": (b.get("label") or "").upper()}
                          for b in layer.get("bombs", []) if "x" in b],
            }
        print(f"{slug}: {sum(1 for s in data['setups'])} sites")

    out_path = ROOT / "data" / "site_markers.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"wrote {out_path} ({len(out)} sites)")


if __name__ == "__main__":
    main()
