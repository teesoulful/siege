#!/usr/bin/env python3
"""
Cross-references data/operator_site_profiles.json (hand-curated, per-player,
preference-ordered operator lists for every site on every ranked map) against
our existing r6prep-derived data/strategies/<map>_defense.json site lists.

r6prep.com's own site-setup coverage is missing one bomb-site combo on 9 of
the 14 maps (confirmed by re-reading data/r6prep_raw/<map>/*_data.json
directly — r6prep's map.sites list itself only has 3 entries there, it's a
real gap in r6prep's coverage, not an extraction bug). The profile file is
more complete, so for those 9 maps this script adds the missing site as a new
entry in data/strategies/<map>_defense.json with empty wall data (the app
already shows "No verified defense setup data yet" for a site with no walls,
and still gets full operator recommendations for it) rather than leaving it
out of the roster entirely.

Writes data/operator_picks.json:
  { mapName: { "Defense": { workingName: { playerId: [op,...] } },
                "Attack":  { workingName: { playerId: [op,...] } } } }
workingName matches data/strategies/<slug>_defense.json sites[].workingName
exactly, so build_data.py can resolve it through the same floor-prefix
display-name logic it already uses for SITE_SETUPS/STRATEGY_BANK.

Usage: python3 scripts/build_operator_picks.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

PLAYER_ID = {"Tee": "tee", "TAMIYM": "tamiym", "Eman": "eman", "Stef": "stefan"}

SLUG_MAP = {
    "Clubhouse": "clubhouse", "Oregon": "oregon", "Bank": "bank", "Chalet": "chalet",
    "Coastline": "coastline", "Border": "border", "Consulate": "consulate",
    "Kafe": "kafe-dostoyevsky", "Lair": "lair", "Nighthaven Labs": "nighthaven-labs",
    "Outback": "outback", "Emerald Plains": "emerald-plains", "Fortress": "fortress",
    "Calypso": "calypso",
}

# The profile file uses the shorthand names players actually say ("Kafe",
# "Calypso"), but data/maps/*.json's canonical "map" field (what
# build_data.py's display_names dict is keyed by) uses the full official
# names — output data/operator_picks.json under the canonical name so
# build_data.py's lookup actually finds it.
CANONICAL_MAP_NAME = {"Kafe": "Kafe Dostoyevsky", "Calypso": "Calypso Casino"}

FLOOR_TOKEN_TO_LABEL = {"B": "Basement", "1F": "1st Floor", "2F": "2nd Floor", "3F": "3rd Floor"}
STOPWORDS = {"the", "a", "an", "of", "and", "or"}


def words(s):
    s = re.sub(r"[—\-/,()']", " ", s)
    return {w.lower() for w in re.findall(r"[A-Za-z]+", s) if w.lower() not in STOPWORDS}


def floor_token(name):
    m = re.search(r"\b(B|1F|2F|3F)\b", name)
    if m:
        return m.group(1)
    if "Basement" in name:
        return "B"
    return None


def clean_room_name(profile_site_key):
    """'Tellers' Office / Archives — 1F' -> 'Tellers' Office / Archives'.
    Also handles per-room floor prefixes like 'B Servers / 1F Tellers' ->
    'Servers / Tellers', since Consulate's profile keys tag each
    slash-separated room individually instead of once at the end."""
    name = re.sub(r"—.*$", "", profile_site_key).strip()
    parts = [re.sub(r"^\s*(B|1F|2F|3F)\s+", "", p.strip()) for p in name.split("/")]
    return " / ".join(p.strip(" —") for p in parts)


MIN_MATCH_SCORE = 3  # below this, treat as no real match rather than a weak guess


def site_score(profile_key, site):
    pf, pw = floor_token(profile_key), words(profile_key)
    of = {"1st Floor": "1F", "2nd Floor": "2F", "3rd Floor": "3F", "Basement": "B"}.get(site["floor"])
    ow = words(site["workingName"]) | {w.lower() for w in site.get("callouts", [])}
    return len(pw & ow) + (2 if of == pf and pf else 0)


def match_sites(profile_keys, our_sites):
    """One-to-one greedy assignment (highest score first) so two different
    profile sites can never both collide onto the same our_sites entry —
    e.g. Bank's 'Tellers' Office / Archives' and 'Open Area / Staff Room'
    both score >0 against our single existing 'Staff Room / Open Area' site,
    but only the real match should claim it; the other is a genuinely
    missing site r6prep never covered."""
    pairs = []
    for pk in profile_keys:
        for site in our_sites:
            score = site_score(pk, site)
            if score >= MIN_MATCH_SCORE:
                pairs.append((score, pk, id(site), site))
    pairs.sort(key=lambda p: -p[0])
    claimed_profile, claimed_site = set(), set()
    result = {}
    for score, pk, site_id, site in pairs:
        if pk in claimed_profile or site_id in claimed_site:
            continue
        result[pk] = site
        claimed_profile.add(pk)
        claimed_site.add(site_id)
    return result


def main():
    profiles = json.loads((DATA / "operator_site_profiles.json").read_text())
    picks_out = {}

    for map_name, slug in SLUG_MAP.items():
        strat_path = DATA / "strategies" / f"{slug}_defense.json"
        strat = json.loads(strat_path.read_text())
        our_sites = strat["sites"]
        profile_sites = profiles[map_name]["sites"]

        working_name_for = {}  # profile site key -> workingName
        new_sites = []

        matched = match_sites(list(profile_sites.keys()), our_sites)
        for site_key in profile_sites:
            m = matched.get(site_key)
            if m is not None:
                working_name_for[site_key] = m["workingName"]
                continue
            # No existing site covers this one — r6prep's own coverage gap.
            # Synthesize a walls-empty site entry so it still shows up as a
            # selectable site with real operator recommendations.
            wn = clean_room_name(site_key)
            ft = floor_token(site_key)
            new_site = {
                "id": slug + "_" + re.sub(r"[^a-z0-9]+", "_", wn.lower()).strip("_"),
                "workingName": wn,
                "floor": FLOOR_TOKEN_TO_LABEL.get(ft, our_sites[0]["floor"]),
                "callouts": [p.strip() for p in wn.split("/")],
                "reinforcements": [], "headHoles": [], "rotates": [], "hatches": [],
                "gadgetPlacements": [], "operatorRecommendations": [], "generalTips": [],
            }
            new_sites.append(new_site)
            working_name_for[site_key] = wn

        if new_sites:
            strat["sites"].extend(new_sites)
            strat_path.write_text(json.dumps(strat, indent=2, ensure_ascii=False))
            print(f"{map_name}: added {len(new_sites)} site(s) missing from r6prep coverage: "
                  f"{[s['workingName'] for s in new_sites]}")

        map_picks = {"Defense": {}, "Attack": {}}
        for site_key, site_data in profile_sites.items():
            wn = working_name_for[site_key]
            for side_key, side_label in (("defense", "Defense"), ("attack", "Attack")):
                map_picks[side_label][wn] = {
                    PLAYER_ID[player]: ops for player, ops in site_data[side_key].items()
                }
        picks_out[CANONICAL_MAP_NAME.get(map_name, map_name)] = map_picks

    out_path = DATA / "operator_picks.json"
    out_path.write_text(json.dumps(picks_out, indent=2, ensure_ascii=False))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
