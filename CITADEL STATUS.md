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
| Names | built | Numbers 0-99, team cities and nicknames, players from a roster file; one clip per voice |
| Director | built (v9.4.0) | citadel-sports `voice-director`; reads `manifest/manifest.json` |
| Wiring | not started | Behind an off-by-default toggle in citadel-sports |

## Next
1. Jordan runs `tools/run.ps1` (then `-Limit 10` first if he wants a quick listen), then `tools/push.ps1`.
2. Listen to the `{team}'s` lines and a few fill-in lines; tune carriers if needed.
3. Create the Vercel project for this repo and replace the placeholder clip host in citadel-sports (`docs/voice-director.md`).

## Order of work
Lines rewrite, then generator, then Voice Director, then wiring. Scheduled after the Intel Hub's first Sunday.

## Plan
https://github.com/mrfaceman23/citadel-hq/blob/main/decisions/2026-10-28-sports-booth-voices-plan.md
