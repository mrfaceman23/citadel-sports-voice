# tools

Makes every Corvus and Bastion clip once, on Jordan's PC, and writes the manifest the Voice Director reads.

## The one line Jordan runs (PowerShell)
```powershell
cd A:\Citadel; if (!(Test-Path citadel-sports-voice)) { git clone https://github.com/mrfaceman23/citadel-sports-voice }; cd citadel-sports-voice; git pull; powershell -ExecutionPolicy Bypass -File .\tools\run.ps1
```
Then, when it says OK: `powershell -ExecutionPolicy Bypass -File .\tools\push.ps1`. Both copy their summary to the clipboard.

Options for `run.ps1`: `-Only idle` (or `events`, `tiers`, `reactions`, `interjections`, `numbers`, `teams`, a trigger like `td`), `-Names roster.json`, `-Limit 10` (quick listen test), `-DryRun` (count only), `-Branch <citadel-sports branch>` (default `preview`; falls back to `voice-director` while preview does not have the speech-ready lines yet), `-Venv <folder>` (default `A:\Citadel\voice-test\venv`).

Needs: the Kokoro venv (Kokoro 0.9.4, soundfile, numpy, espeak-ng), Node, git, and ffmpeg (`winget install Gyan.FFmpeg`; without it the clips stay .wav and are not committed). It uses the graphics card when the venv's PyTorch has CUDA; the first lines it prints say `on cuda` or `on cpu`.

## Files
| File | What it does |
|---|---|
| `run.ps1` | Gets the latest `booth-lines.js` from citadel-sports, runs the generator, checks the manifest, copies a summary |
| `push.ps1` | Commits the clips and manifest and pushes to `main` |
| `generate.py` | The generator (Python: stdlib + kokoro + soundfile + numpy; ffmpeg for .ogg) |
| `export-lines.mjs` | Reads `booth-lines.js` (its exports) and writes the JSON the generator uses |
| `validate-manifest.mjs` | Checks `manifest/manifest.json`: schema, files exist (`--files`), and every line lines up with the Director (`--lines booth-lines.js`) |

## How a line becomes clips
1. `speechPieces(line)` from `booth-lines.js`. Text between marks is one clip, split exactly where the Voice Director splits it (at `[pause:ms]`, `{fill-ins}` and `[overlap]`; `*actions*` are never spoken).
2. **Carriers.** A piece next to a fill-in is said inside a sentence and then cut out, so it keeps its natural rhythm: `Touchdown {team}.` is said as "Touchdown Taylor." and "Taylor." is cut away. Names and numbers are said as "Then Josh Jacobs again." and cut out. A piece split by `[overlap]` mid-sentence uses its real neighbouring words. The cut point comes from Kokoro's word timings; if a cut looks wrong (length far from the same words said alone) the plain take is used and counted in the summary.
3. Edge silence trimmed at -45 dBFS, levelled to about -18 dBFS speech RMS (roughly -16 to -18 LUFS; it is an RMS estimate, not a true loudness meter), peaks capped at -1 dBFS, 5 ms fades, then 25 ms of silence kept at both ends so the Director's 20 ms crossfade never clips a word.
4. 24 kHz mono WAV in `tmp/wav/`, then `.ogg` (Opus 48 kbps) next to the line's folder.
5. Punctuation-only pieces (the "." in `{score}.`) point to `common/_blank.ogg` (60 ms of silence).

## Intensity (tiers)
Kokoro has no emotion control, so the three tiers are pace and volume only: tier 1 (flat) 3% slower, tier 2 normal, tier 3 (losing it) 4% faster and +2 dB. Plain booth lines are tier 2. The Voice Director also levels every clip and adds its own +/-2 dB per tier when it plays, so most of the audible difference comes from the pace and from the words themselves (Bastion's capitals are read normally; Kokoro would spell them letter by letter).

## Generate once
Every clip has a hash of its text, carriers, voice, speed and tier (`manifest/hashes.json`). A re-run skips unchanged clips, copies a clip whose exact text already exists elsewhere, renders only new or changed ones, and (on a full run) removes clips it made earlier whose line is gone. Clips it did not make are never deleted.

## Names, numbers, teams
Each is made once per voice. Keys follow the Director's `slug()`: `josh-jacobs@corvus`, `17@bastion`, `kansas-city@corvus`, `the-chiefs@bastion`. Teams come from `TEAMS` in `booth-lines.js` (city, and "the" + nickname, which is what the booth says). The roster for `-Names` is `[{ "id": "...", "name": "Josh Jacobs", "team": "GB" }]`.

## Known rough spots
- `{team}'s ...` (19 lines): the "'s" is cut from the end of the carrier, so it can sound clipped. Listen to these first.
- Fill-ins like `{score}`, `{clock}`, `{downDist}` need clips the generator does not make yet (numbers 0-99 cover single numbers only). Lines whose fill-in has no clip are skipped for sound by the Director, never half-played.

## Testing without the PyTorch model
`--engine onnx --onnx-dir <folder with kokoro-v1.0.onnx and voices-v1.0.bin>` uses kokoro-onnx (same voices, no word timings, so carriers are cut by lining up the carrier word against the sentence). Only for test machines; Jordan's PC uses the normal Kokoro engine.
