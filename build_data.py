#!/usr/bin/env python3
"""
Builds dist/data.js from the source-of-truth JSON files in data/.

Run this after editing anything under data/ (new transcript parsed into
data/strategies/<map>.json, wiki updates to data/operators.json, etc.)
and then just refresh the browser tab — index.html loads dist/data.js as
a plain <script> tag so it works over file:// with no local server
required.

Usage: python3 build_data.py
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
DIST = ROOT / "dist"


def load_json(path):
    with open(path) as f:
        return json.load(f)


OPERATOR_ALIASES = {
    "Jager": "Jäger", "Fuse": "Fuze", "Monty": "Montagne",
    "Capitao": "Capitão", "Nokk": "Nøkk", "Tubarao": "Tubarão",
}


def split_operator_names(raw, known_sides):
    """Transcript-derived 'operator' fields are often 'Hibana or Ace' /
    'Azami or Frost' style either/or picks, or generic/uncertain
    placeholders like 'DMR-capable defender' or 'Unconfirmed (source
    audio: wai)'. STRATEGY_BANK/getRecommended need one real,
    individually pickable, ban-able operator per entry — anything that
    isn't a real, confirmed operator name breaks pick/ban lookups
    downstream (can never be banned, never matches a real selection) and
    would wrongly let the app auto-assign a squad member to an operator
    identity nobody actually confirmed. Split on common separators, apply
    known nickname/spelling aliases, and DROP tokens that still don't
    resolve to a real operator rather than keeping the raw string as a
    fake pickable entry — the full detail stays intact in SITE_SETUPS
    either way, this only controls what's offered as an auto-pick."""
    names = []
    for token in re.split(r",| or | and |/", raw):
        token = token.strip().strip("()")
        token = OPERATOR_ALIASES.get(token, token)
        if token in known_sides:
            names.append(token)
    return names


def floor_prefix(map_floors, raw_floor_text):
    """In-game floor labels are B / 1F / 2F / 3F. Our strategy data's
    'floor' field is free text pulled from each transcript ('Top Floor',
    'Ground Floor (with upstairs presence required)', etc.), so map it onto
    the wiki-verified per-map floor list (data/maps/*.json) to get the
    right number for THIS map — 'Top Floor' is 2F on a 3-floor map like
    Bank but 3F on Kafe Dostoyevsky, which actually has three floors."""
    text = (raw_floor_text or "").lower()
    non_basement = [f for f in map_floors if "basement" not in f.lower()]
    if "basement" in text:
        return "B"
    if "ground" in text:
        return "1F" if non_basement else ""
    if "top" in text:
        n = len(non_basement)
        return f"{n}F" if n else ""
    if "1st" in text or "first" in text:
        return "1F"
    if "2nd" in text or "second" in text:
        return "2F"
    if "3rd" in text or "third" in text:
        return "3F"
    return ""


def build():
    operators = load_json(DATA / "operators.json")

    maps = {}
    for path in sorted((DATA / "maps").glob("*.json")):
        m = load_json(path)
        maps[m["map"]] = m

    strategies = {}
    general_principles = []
    for path in sorted((DATA / "strategies").glob("*.json")):
        s = load_json(path)
        if s.get("type") == "general_principles":
            general_principles.append(s)
            continue
        strategies.setdefault(s["map"], {})[s["side"]] = s

    # Legacy STRATEGY_BANK[map][side][site_name][operator] = {role, job, synergy}
    # generated from the richer site-setup data so the existing per-operator
    # UI (renderInstructions, getRecommended) keeps working unchanged.
    strategy_bank = {}
    display_names = {}  # map_name -> {workingName: "2F CEO Office / ..."}
    for map_name, sides in strategies.items():
        strategy_bank.setdefault(map_name, {"sites": []})
        map_floors = maps.get(map_name, {}).get("floors", [])
        display_names.setdefault(map_name, {})
        # union site names across every side's file so the site picker shows
        # every known site even if only one side has data for some of them.
        # The floor prefix is fixed the first time a workingName is seen and
        # reused for every side after that, so Defense/Attack never end up
        # with two different display strings for the same physical site.
        seen = set(strategy_bank[map_name]["sites"])
        for side, side_data in sides.items():
            for s in side_data["sites"]:
                if s["workingName"] not in seen:
                    seen.add(s["workingName"])
                    prefix = floor_prefix(map_floors, s.get("floor"))
                    display = f"{prefix} {s['workingName']}".strip() if prefix else s["workingName"]
                    display_names[map_name][s["workingName"]] = display
                    strategy_bank[map_name]["sites"].append(display)
        for side, side_data in sides.items():
            strategy_bank[map_name].setdefault(side, {})
            for site in side_data["sites"]:
                display = display_names[map_name][site["workingName"]]
                entry = {}
                for rec in site.get("operatorRecommendations", []):
                    for name in split_operator_names(rec["operator"], operators["sides"]):
                        entry[name] = {
                            "role": rec["role"],
                            "job": rec["note"],
                            "synergy": [],
                        }
                strategy_bank[map_name][side][display] = entry

    # SITE_SETUPS[map][side][site_name] = full structured detail
    site_setups = {}
    for map_name, sides in strategies.items():
        site_setups.setdefault(map_name, {})
        for side, side_data in sides.items():
            site_setups[map_name].setdefault(side, {})
            for site in side_data["sites"]:
                display = display_names[map_name][site["workingName"]]
                site_setups[map_name][side][display] = site

    DIST.mkdir(exist_ok=True)
    out = DIST / "data.js"
    with open(out, "w") as f:
        f.write("// AUTO-GENERATED by build_data.py — do not edit by hand.\n")
        f.write("window.SIEGE_OPERATORS = " + json.dumps(operators["sides"]) + ";\n")
        f.write("window.SIEGE_OPERATOR_UTILITY = " + json.dumps(operators["utility"]) + ";\n")
        f.write("window.SIEGE_MAPS = " + json.dumps(maps) + ";\n")
        f.write("window.SIEGE_STRATEGY_BANK = " + json.dumps(strategy_bank) + ";\n")
        f.write("window.SIEGE_SITE_SETUPS = " + json.dumps(site_setups) + ";\n")
        f.write("window.SIEGE_GENERAL_PRINCIPLES = " + json.dumps(general_principles) + ";\n")
    print(f"Wrote {out}")


if __name__ == "__main__":
    build()
