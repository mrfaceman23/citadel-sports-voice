# Citadel Sports Voice: Status · v0.1.0 · updated 2026-10-29

**5% scaffolded.** The folders, README and manifest plan exist. No clips are committed yet.

## Where it stands
- Voices chosen by Jordan after listening: Corvus = `bm_fable` (speed about 0.93), Bastion = `am_michael` (speed about 1.10).
- Tested on Jordan's PC at `A:\Citadel\voice-test` (Kokoro 0.9.4, 60 tasting clips). Those test clips are not in this repo.
- Clip format: .ogg, mono, 48 kbps. No .wav committed.

## Components
| Component | Status | Notes |
|---|---|---|
| Lines rewrite | not started | Rewrite `booth-lines.js` for speech with explicit pause marks |
| Generator | not started | Lands in `tools/`; splits at pause marks, trims silence, makes .ogg |
| Names | not started | Team and player name clips |
| Director | not started | Voice Director lives in citadel-sports; reads `manifest/` |
| Wiring | not started | Behind an off-by-default toggle in citadel-sports |

## Order of work
Lines rewrite, then generator, then Voice Director, then wiring. Scheduled after the Intel Hub's first Sunday.

## Plan
https://github.com/mrfaceman23/citadel-hq/blob/main/decisions/2026-10-28-sports-booth-voices-plan.md
