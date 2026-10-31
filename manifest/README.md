# manifest

`manifest.json` is the index the Voice Director (citadel-sports `App/assets/voice-director.js`) reads. It is written by `tools/generate.py` and checked by `tools/validate-manifest.mjs`. `hashes.json` is the generator's record of every clip it made (for "generate once"); the app does not read it. `sample-manifest.json` is a small real example (10 lines, 5 names, numbers 0-9) for tests.

## Top level
```json
{
  "version": 1,
  "base": "../",
  "voices": { "corvus": { "voice": "bm_fable", "speed": 0.93 }, "bastion": { "voice": "am_michael", "speed": 1.1 } },
  "tiers": { "1": { "speed": 0.97, "gain_db": 0 }, "2": { "speed": 1, "gain_db": 0 }, "3": { "speed": 1.04, "gain_db": 2 } },
  "slot_estimate_ms": 400,
  "lines": [ ... ],
  "names": { "josh-jacobs@corvus": "names/josh_jacobs_c.ogg", "josh-jacobs@bastion": "names/josh_jacobs_b.ogg" },
  "common": { "17@corvus": "common/num_17_c.ogg", "kansas-city@bastion": "common/team_kc_city_b.ogg" },
  "reactions": { "b-roar-2": "reactions/bastion/b-roar-2.ogg" },
  "interjections": { "b-woah": "interjections/bastion/b-woah.ogg" }
}
```
- `base`: clip paths are relative to the repo root; `"../"` means one folder up from `manifest/`. The Director resolves a relative base from where it loaded the manifest.
- `names` / `common`: key = the Director's `slug()` of the fill-in value, plus `@corvus` or `@bastion` (one clip per voice). The Director tries the speaking voice's key first, then the plain slug.
- `reactions` / `interjections`: keyed by the ids in `booth-lines.js`.

## One line entry
```json
{
  "id": "td:corvus:t1:0",
  "character": "corvus",
  "text": "+Touchdown {team}. [pause:420] [overlap] {player} finishes the drive. [pause:420] {score}.",
  "trigger": "td",
  "group": "tiers",
  "pieces": [
    { "file": "lines/corvus/td_t1_0__01.ogg", "text": "Touchdown", "sha": "d94f4501e3f7c558", "ms": 723 },
    { "slot": "team" },
    { "file": "common/_blank.ogg", "text": ".", "sha": "blank60", "ms": 60 },
    { "slot": "player" },
    { "file": "lines/corvus/td_t1_0__03.ogg", "text": "finishes the drive.", "sha": "9cd2abde02e74c92", "ms": 1302 },
    { "slot": "score" },
    { "file": "common/_blank.ogg", "text": ".", "sha": "blank60", "ms": 60 }
  ],
  "pauses": [0, 0, 420, 0, 420, 0],
  "intensity": 1,
  "overlap_piece": 3,
  "overlap_ms": 1603,
  "duration_ms": 4185,
  "sha": "5c28c5d29f73bb93"
}
```

## Fields
- `id`: the booth key, as `say()` returns it: `trigger:character:index`, or `trigger:character:tN:index` for intensity tiers. Clip files use it without the character (`td_t1_0__01.ogg`).
- `character`: `corvus` or `bastion`.
- `text`: the line exactly as in `booth-lines.js` (mood, marks and `{fill-ins}` included). The Director can also find a line by this text.
- `pieces[]`: in play order. A clip (`file`, `text`, `sha`, `ms`) or a fill-in (`slot`) filled from `names`/`common`. Pieces split exactly where the Director splits a line: at pauses, fill-ins and the overlap mark.
- `pauses`: gap in ms after each piece (one fewer than pieces), from the `[pause:ms]` marks. The Director takes the gaps from the line itself; these are for reference and for `duration_ms`.
- `intensity`: 1 flat, 2 normal (every plain line), 3 losing it. Tier lines are made at their tier's pace and volume.
- `overlap_piece` / `overlap_ms`: where the other voice may come in (the `[overlap]` mark), as a piece index and as ms from the start.
- `duration_ms`: clips + pauses, with each fill-in counted as `slot_estimate_ms`.
- `sha`: hash of the pieces' hashes and pauses; changes whenever any clip of the line changes.
