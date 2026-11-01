# Citadel Sports Voice: Status · v0.2.0 · updated 2026-10-31

**30%: generator built, no clips yet.** `tools/` can make every clip and the manifest; Jordan runs it once on his PC (see `tools/README.md`).

## Where it stands
- Voices chosen by Jordan after listening: Corvus = `bm_fable` (speed about 0.93), Bastion = `am_michael` (speed about 1.10).
- Tested on Jordan's PC at `A:\Citadel\voice-test` (Kokoro 0.9.4, 60 tasting clips). Those test clips are not in this repo.
- Clip format: .ogg, mono, 48 kbps. No .wav committed.

## Components
| Component | Status | Notes |
|---|---|---|
| Lines rewrite | done | citadel-sports v9.3.2 (`booth-lines-speech`): pause/overlap marks, tiers, reactions, interjections |
| Generator | built, tested on CPU | `tools/generate.py` + `run.ps1` / `push.ps1`. Tested here with kokoro-onnx (same voices); first real run on Jordan's PC |
| Names | built | Numbers 0-99, team cities and nicknames, players from a roster file (or `-Sleeper` from the two leagues); one clip per voice |
| Vocab | 142 made on Jordan's PC, not pushed (push.ps1 skipped `vocab/` until v10.2); 176 more to make | `tools/vocab.json`: 159 words = 318 clips; `run.ps1 -Only vocab`, then `push.ps1` |
| Director | built (v9.4.0) | citadel-sports `voice-director`; reads `manifest/manifest.json` |
| Wiring | not started | Behind an off-by-default toggle in citadel-sports |

## Next
0. After `fillin-vocab-2` merges: the one PowerShell block in `README.md` (git pull, `run.ps1 -Only vocab`, `push.ps1`).
1. Jordan runs `tools/run.ps1` (then `-Limit 10` first if he wants a quick listen), then `tools/push.ps1`.
2. Listen to the `{team}'s` lines and a few fill-in lines; tune carriers if needed.
3. Create the Vercel project for this repo and replace the placeholder clip host in citadel-sports (`docs/voice-director.md`).

## Log
- 2026-11-01: `fillin-vocab-2`: 88 new vocab words (176 clips) for the Director's v10.2 stitching ({clock}, {downDist}, minus/point/half, {spot}, {tiedAt}, {ogFinal}, positions, injury status, weather, field/roof, records, game slots); validator warns on vocab words with no clip and errors on vocab clips outside `vocab/`. Fix: `push.ps1` now adds `vocab/` (the 142 vocab clips made on Jordan's PC were never pushed, so the live manifest pointed at missing files). Pairs with citadel-sports `voice-fillins-2`. Stand-in engine test: dry run 176 to render, second run 0.
- 2026-10-31: `fillin-vocab`: vocab group (`tools/vocab.json`, manifest `vocab` map, validator), `tools/sleeper-roster.py` + `run.ps1 -Sleeper [-AllActive]` for player names, dry-run prints new clips per folder. Pairs with citadel-sports `voice-fillins` (the Director stitches scores and numbers from existing clips). Next: Jordan runs vocab + Sleeper names, then push.

## Order of work
Lines rewrite, then generator, then Voice Director, then wiring. Scheduled after the Intel Hub's first Sunday.

## Plan
https://github.com/mrfaceman23/citadel-hq/blob/main/decisions/2026-10-28-sports-booth-voices-plan.md
