# Changelog

## 0.2.0 — 2026-10-31
- Generator built (`tools/generate.py`, `run.ps1`, `push.ps1`) for audio clips and manifest generation with Kokoro TTS (Corvus `bm_fable`, Bastion `am_michael`).
- Manifest schema and manifest validator (`tools/validate-manifest.js`).
- Vocab clips generated for situations, clock, down/distance, ordinals, flags, team names, and Sleeper league rosters (`tools/sleeper-roster.py`).
- Spoken member spelling added (`{text, say}`) for custom member names (PR #4, 2026-11-03).

## 0.1.0 — 2026-10-29
- Initial repository scaffolding: project layout, manifest schema, tools placeholder, README, and status tracking (commit `fadf357`).
