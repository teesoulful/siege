# Transcript → strategy JSON parsing spec

You are converting one R6 Siege YouTube setup-guide transcript into a structured
JSON strategy file for a real-time strategy lookup app. Read
`data/strategies/bank.json` first — it is the canonical worked example (Bank,
Defense side) and your output must match its exact shape and field names:

```
{
  "map": "<Map Name>",
  "side": "Defense" | "Attack",
  "source": {
    "title": "<video title, or your best inference of the topic if title unknown>",
    "type": "youtube_transcript",
    "file": "data/raw_transcripts/<the txt file you read>",
    "notes": "<anything a reader should know before trusting this — ASR quality, missing sections, etc.>"
  },
  "sites": [
    {
      "id": "kebab-case-id",
      "workingName": "Room A / Room B",
      "floor": "Top Floor" | "Ground Floor" | "Basement" | etc (use the map's own floor structure),
      "callouts": ["Room names mentioned for this site"],
      "reinforcements": [{"location": "...", "note": "...", "timestamp": "MM:SS"}],
      "headHoles": [{"location": "...", "note": "...", "timestamp": "MM:SS"}],
      "rotates": [{"location": "...", "note": "...", "timestamp": "MM:SS"}],
      "hatches": [{"location": "...", "note": "...", "timestamp": "MM:SS"}],
      "gadgetPlacements": [{"location": "...", "operator": "...", "note": "...", "timestamp": "MM:SS"}],
      "operatorRecommendations": [{"operator": "...", "role": "...", "note": "..."}],
      "generalTips": [{"note": "...", "timestamp": "MM:SS"}]
    }
  ]
}
```

## Ground rules (non-negotiable — read the Bank example to see these applied)

1. **Never invent content.** Every entry must trace back to something actually
   said in the transcript you were given, with a real `timestamp`. If a whole
   category (e.g. `hatches`) has nothing in the transcript for a site, omit the
   key or leave the array empty — do not pad it with plausible-sounding filler.

2. **These are auto-generated YouTube captions — expect ASR errors, especially
   on operator names and R6 jargon.** When a name is ambiguous or doesn't match
   a real operator on that side, do NOT silently pick the closest-sounding real
   operator and present it as fact. Either:
   - use context (what gadget/role is being described) to identify the operator
     with reasonable confidence and proceed normally, or
   - if you genuinely can't tell, say so in the `note` (e.g. "source audio named
     an operator phonetically as 'X' which doesn't match a real defender —
     treat as unconfirmed") rather than guessing a specific operator's name.
   Getting an operator's SIDE wrong (e.g. recommending an Attack-only operator
   for a Defense site) is the single worst failure mode — double check every
   operator you name against real R6 Siege rosters and the stated `side` of
   the file you're writing.

3. **Site structure**: figure out the map's actual bombsite pairs and floors
   from how the video itself organizes its walkthrough (it will move
   site-by-site, usually announcing each one). Use the video's own room/callout
   names (informal is fine, that's what a squad actually says out loud) as
   `workingName`/`callouts` — you don't have wiki access to get canonical names,
   so don't invent official-sounding names you're not sure of.

4. **Be thorough but atomic.** Break the walkthrough into many small, specific
   items rather than a few giant paragraphs — a squad glancing at this mid-round
   needs to scan it fast. Aim for the same density as the Bank example (roughly
   5-10 reinforcements, several head holes/rotates/hatches, a handful of
   gadget placements and operator recs, several general tips, PER site).

5. **Attack-side files** will naturally lean more on `gadgetPlacements` (breach
   charge placement, drone paths, utility usage) and `operatorRecommendations`
   (who opens what) rather than `reinforcements`/`hatches` (those are
   defense-only concepts) — adapt the schema sensibly; it's fine for an
   attack-side site entry to have empty `reinforcements`/`hatches` arrays.

6. **When you're done**, validate the JSON parses (`python3 -c "import json;
   json.load(open('...'))"`) before finishing, and report back only a short
   summary (map, side, site count, item count, any operator-side ambiguities
   you flagged) — not the full JSON content.

7. **A wall segment is either reinforced or head-holed — never both.**
   Reinforcing a wall makes it fully hard: no bullets, no holes of any kind
   go through it. Head holes / feet holes only exist on soft (unreinforced)
   walls. So the exact same `location` string must never appear in both
   `reinforcements`/`hatches` and `headHoles`/`rotates` for one site —
   `build_data.py` now fails the build if it finds this (see
   `check_no_reinforce_headhole_conflict`).
   - If a transcript describes reinforcing part of a wall and head-holing a
     *different* part of the same described wall (a real, common technique —
     e.g. reinforce the left panel, head-hole the right panel), give the two
     actions clearly distinct `location` strings ("...Left Side" /
     "...Right Side", or name the two sub-features separately) so it's
     obvious they're different physical spots, not a contradiction.
   - If the creator presents reinforcing vs. head-holing as alternative
     *choices* for the same spot ("you can either reinforce this or make
     head holes — I prefer X"), that is ONE entry, not two — pick whichever
     the creator actually recommends (or the one played most often) and put
     it under the correct single category. Don't duplicate the same spot
     into both arrays just because the transcript mentions both options.

## Output location

Write to `data/strategies/<map-slug>_<side-lowercase>.json`, e.g.
`data/strategies/calypso_defense.json`. Map slug = lowercase, spaces to
hyphens (e.g. "Kafe Dostoyevsky" → `kafe-dostoyevsky`).

## Rewrite pass — bringing an existing file up to the Bank standard

Bank went through several rounds of live-testing feedback that produced rules
beyond the base parsing spec above. When asked to bring another map's
already-parsed file up to the same standard, apply all of these. Read the
CURRENT `data/strategies/bank.json` and `bank_attack.json` as the worked
example — they already reflect every rule below.

8. **Locations are compass direction + room**, e.g. "South Wall of Garage",
   "West Wall of CEO Office, Left Side". Standard top-down map convention:
   north is up on the map, no explicit compass rose needed (confirmed
   sufficient grounding by the app's owner). To assign compass directions
   accurately, get a real top-down blueprint image for the map — the same
   Ubisoft source used for Bank's blueprints — and reason from the actual
   floor plan, not from guessing. **If you cannot get reliable spatial
   grounding for a given site (no usable blueprint, transcript too vague
   about orientation), do NOT invent a compass direction** — leave the
   location as the room/feature name only (no compass prefix) rather than
   fabricate one. A missing compass prefix is honest; a wrong one is worse
   than useless in a live callout.

9. **No reasoning or hedging in notes — bare actions plus short tactical
   cues only.** Cut "why it matters," "this is important because," "lets you
   hold X because Y" style justification entirely. Keep: the action itself
   ("Shoot the top of the wall and C4 over it"), and short in-the-moment
   warnings ("Watch the west repel spot outside these windows") — those are
   operational, not explanatory. Test: if a sentence explains WHY a spot
   matters rather than WHAT to do or watch for, cut it.
   - Bad: "Reinforcing both this wall and the CEO wall lets attackers walk
     straight into Square unopposed — head holes onto Janitor are the only
     remaining angle, which is why they matter."
   - Good: "Don't reinforce this and the CEO wall both — leaves Square wide
     open. Keep head holes onto Janitor."

10. **`operatorRecommendations` entries need a `holdLocation` field** — a
    short, real room/spot name (e.g. "Meeting Room Desks", "Kanto Wall
    Corridor"), not the abstract `role` word ("Anchor"). The app displays
    `holdLocation` as the primary label for the Defend section so a player
    can read it and know exactly where to stand without opening the detail.

11. **Same-wall reinforce + head-hole/rotate pairs need matching, distinct
    names** so the app's automatic pairing (which keeps them on one
    player's card) can find them: strip to the same base name before any
    qualifier, e.g. `"West Wall of CEO Office, Left Side"` (reinforce) /
    `"West Wall of CEO Office, Right Side"` (head hole) — the app matches on
    everything before the first comma, case-insensitively. Don't reuse the
    literal identical string for both (that's the rule-8-in-the-old-spec
    conflict) and don't let two genuinely different walls share a base name
    just because they're in the same room (that forces them onto one
    player's card incorrectly — see rule 7 above and the "Wall at Back of
    CEO Office" vs "West Wall of CEO Office" distinction in bank.json).

12. **After rewriting, validate your own file only** — don't run
    `python3 build_data.py` yourself. It rebuilds `dist/data.js` from every
    strategy file in the project at once and other maps' rewrite passes are
    likely running concurrently, so invoking the shared build script mid-way
    risks reading another file while it's still being edited. Instead:
    - `python3 -c "import json; json.load(open('data/strategies/<your file>'))"`
      for syntax.
    - Self-check the reinforce/head-hole rule (item 7) on your own file with:
      ```python
      import json
      s = json.load(open('data/strategies/<your file>'))
      for site in s['sites']:
          hard = {i['location'].strip().lower() for i in site.get('reinforcements', []) + site.get('hatches', [])}
          soft = {i['location'].strip().lower() for i in site.get('headHoles', []) + site.get('rotates', [])}
          overlap = hard & soft
          if overlap: print(site['id'], overlap)
      ```
      Fix anything it prints before reporting done. The project owner runs
      the full `build_data.py` once after all rewrite passes finish.

13. **New operators not yet in `data/operator_gadgets.json`**: if a site's
    `operatorRecommendations` names an operator not already present in that
    file (it currently covers Bank's 24), do NOT edit that file yourself —
    it's shared across every map's rewrite pass running at the same time and
    concurrent edits will clobber each other. Just list the new operator
    names in your final report; gadget research for them happens in one
    consolidated pass afterward.
