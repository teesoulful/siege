#!/usr/bin/env python3
"""
Downloads YouTube auto-captions via yt-dlp and cleans them into the same
[mm:ss]-paragraph style as the hand-provided Bank transcript, so every
transcript in data/raw_transcripts/ can be parsed the same way.

Requires: yt-dlp, certifi (both pip --user installed already in this env).
Usage: python3 scripts/fetch_transcripts.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
OUT_DIR = ROOT / "data" / "raw_transcripts"
YT_DLP = str(pathlib.Path.home() / "Library/Python/3.14/bin/yt-dlp")

VIDEOS = [
    # (video_id, map, side)
    ("qf3AthSTIDQ", "Calypso", "Defense"),
    ("oK4VcBrntmI", "Fortress", "Defense"),
    ("_5SRuXkYjI8", "Skyscraper", "Defense"),
    ("LITKieiA8pc", "Nighthaven Labs", "Defense"),
    ("F6kIn15m1-A", "Border", "Defense"),
    ("1m1M_DE5xkM", "Kafe Dostoyevsky", "Defense"),
    ("m3LDBYn8LAI", "Clubhouse", "Defense"),
    ("jV3bcAsK2s0", "Oregon", "Defense"),
    ("fkBuc1IDudk", "Chalet", "Defense"),
    ("bCwBtQxq3qg", "Consulate", "Defense"),
    ("kGoc1PlyeNQ", "Outback", "Defense"),
    ("Ts95moV8NZw", "Villa", "Defense"),
    ("JYazTzzIuok", "Coastline", "Defense"),
    ("Vmxlp9Z0T5o", "Theme Park", "Defense"),
    ("TIIUUKPZfUA", "Kanal", "Defense"),
    ("ppWvSNEl9f0", "Border", "Defense_v2"),
    ("g1xo4KLFpCY", "Nighthaven Labs", "Attack"),
    ("k1S5BGxqrzA", "Calypso", "Attack"),
    ("LJuBBBbleO8", "Border", "Attack"),
    ("HbuIlZSNz1U", "Bank", "Attack"),
    ("neKWknwvP3E", "Kafe Dostoyevsky", "Attack"),
    ("tuxzyDCx-OI", "Coastline", "Attack"),
    ("sUJ2k7JVFIU", "Oregon", "Attack"),
    ("RP5wiovuM30", "Chalet", "Attack"),
    ("dgRssgNFTVY", "Clubhouse", "Attack"),
    ("2UOJdDIUtKU", "General", "Attack"),
]


def _overlap_len(a, b):
    """Longest suffix of a that is a prefix of b (word-aligned)."""
    aw, bw = a.split(), b.split()
    max_k = min(len(aw), len(bw), 40)
    for k in range(max_k, 0, -1):
        if aw[-k:] == bw[:k]:
            return k
    return 0


def vtt_to_clean_text(vtt_path):
    """Collapse YouTube's rolling-caption VTT into deduped continuous text
    with [mm:ss] markers roughly every ~20s, matching the Bank transcript
    style so the same parsing approach applies to every file. YouTube's
    auto-caption cues are a growing/rolling buffer (each cue repeats most of
    the previous cue's words plus a few new ones), so cues are merged by
    finding the word-level overlap between consecutive cues rather than
    trusting line boundaries, which are not reliable dedupe markers."""
    text = pathlib.Path(vtt_path).read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\n\n+", text)
    ts_re = re.compile(r"(\d\d):(\d\d):(\d\d)\.(\d\d\d) --> (\d\d):(\d\d):(\d\d)\.(\d\d\d)")

    cues = []  # (start_seconds, text)
    for block in blocks:
        lines = block.strip().split("\n")
        if not lines or "-->" not in lines[0]:
            continue
        m = ts_re.match(lines[0])
        if not m:
            continue
        h, mi, s, ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        start = h * 3600 + mi * 60 + s + ms / 1000
        body = " ".join(lines[1:])
        body = re.sub(r"<[^>]+>", "", body)
        body = re.sub(r"\s+", " ", body).strip()
        if body:
            cues.append((start, body))

    if not cues:
        return ""

    accumulated_words = []
    timestamped_words = []  # (seconds, word)
    prev_text = ""
    for start, body in cues:
        k = _overlap_len(prev_text, body)
        new_words = body.split()[k:]
        for w in new_words:
            timestamped_words.append((start, w))
        prev_text = body

    # merge into ~20s paragraphs
    out = []
    para_start = timestamped_words[0][0]
    para_words = []
    for t, w in timestamped_words:
        if t - para_start > 20 and para_words:
            out.append((para_start, " ".join(para_words)))
            para_start = t
            para_words = []
        para_words.append(w)
    if para_words:
        out.append((para_start, " ".join(para_words)))

    result = []
    for t, line in out:
        mm = int(t // 60)
        ss = int(t % 60)
        result.append(f"[{mm:02d}:{ss:02d}]\n{line}\n")
    return "\n".join(result)


def fetch_one(video_id, map_name, side):
    safe_map = map_name.replace(" ", "_")
    out_stub = f"{safe_map}_{side}_{video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            YT_DLP, "--write-auto-sub", "--sub-lang", "en", "--skip-download",
            "--sub-format", "vtt", "-o", f"{tmp}/raw",
            f"https://www.youtube.com/watch?v={video_id}",
        ]
        env = dict(os.environ)
        try:
            import certifi
            env["SSL_CERT_FILE"] = certifi.where()
        except ImportError:
            pass
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
        vtt_files = list(pathlib.Path(tmp).glob("*.vtt"))
        if not vtt_files:
            print(f"FAILED {out_stub}: {r.stderr[-800:]}")
            return False
        cleaned = vtt_to_clean_text(vtt_files[0])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUT_DIR / f"{out_stub}.txt"
        dest.write_text(
            f"Source: https://www.youtube.com/watch?v={video_id}\nMap: {map_name}\nSide: {side}\n\n{cleaned}",
            encoding="utf-8",
        )
        print(f"OK {out_stub} -> {dest} ({len(cleaned)} chars)")
        return True


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    ok, fail = 0, 0
    for video_id, map_name, side in VIDEOS:
        if only and video_id not in only:
            continue
        if fetch_one(video_id, map_name, side):
            ok += 1
        else:
            fail += 1
    print(f"\nDone: {ok} ok, {fail} failed")


if __name__ == "__main__":
    main()
