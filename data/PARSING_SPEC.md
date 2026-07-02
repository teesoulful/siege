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

## Output location

Write to `data/strategies/<map-slug>_<side-lowercase>.json`, e.g.
`data/strategies/calypso_defense.json`. Map slug = lowercase, spaces to
hyphens (e.g. "Kafe Dostoyevsky" → `kafe-dostoyevsky`).
