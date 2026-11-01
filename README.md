# citadel-sports-voice

The spoken voices for Corvus and Bastion, the two booth characters in Citadel Sports. This repo holds only the audio and the index that points to it. The app code lives in `citadel-sports`.

## The one-generation rule
Every clip is generated once, here, on Jordan's PC. The app never asks a voice engine for anything while it is open. It plays finished clips and glues them together in the browser. If a line changes, that one clip is regenerated and committed. Nothing else is touched.

## Voices
- **Corvus**: Kokoro voice `bm_fable`, speed about 0.93.
- **Bastion**: Kokoro voice `am_michael`, speed about 1.10.

Kokoro does not pause at commas, so pacing never comes from punctuation. Every line has explicit pause marks (like `[pause:250]`). The generator makes one clip per piece and the app puts the chosen gaps between them. Silence at clip edges is trimmed.

## Making the clips
One PowerShell line on Jordan's PC, then `tools\push.ps1`. Details and options: `tools/README.md`.

## Fill-ins (vocab and player names)
Lines like "Touchdown {team}. {player} finishes the drive. {score}." need a clip for every blank. The app builds a score out of the team and number clips ("Green Bay" "27" ... "Carolina" "19"), so those are covered. The rest comes from two runs:
- **Vocab** (`-Only vocab`): every word in `tools/vocab.json`, one clip per voice: penalties (`{flag}`), Lase and Greatness (`{member}`), deep/short (`{depth}`), left/right/middle (`{dir}`), run lanes (`{lane}`), "first quarter"..."overtime" (`{pqtr}`), "first"..."twelfth" (`{nth}`), and "to", "hundred", "quarter" for building scores and quarters. Since v10.2 also the words for the game clock ("minutes", "seconds", "oh"), down and distance ("and goal", "and inches"), "minus" / "point" / "and a half", field spots ("its own", "midfield"), "tied at" / "beat", and the fixed word lists the booth uses (positions, injury status, weather, field and roof, covered/won/lost, game slots). 159 words = 318 clips (176 new). Plain words only: Kokoro ignores commas, so the app adds the gaps.
- **Player names** (`-Sleeper`): makes `tmp\roster.json` from your two Sleeper leagues (everyone rostered, plus Sleeper's most-added players of the day, plus any names you list) and records each name once per voice. The first time, it creates `tools\leagues.local.json` and stops: open it, put the two league ids in `"leagues"` (the number in the league's web address on sleeper.com), save, run again. That file never goes to GitHub. Add `-AllActive` to also record every active QB/RB/WR/TE/K in the NFL (about 700 names, so any scorer in any game is covered). You can also hand it your own file: `-Names my-roster.json` with `[{ "id": "...", "name": "Josh Jacobs", "team": "GB" }]`.

Re-runs only make clips that are new (a new word in vocab.json, a new player on a roster). `-DryRun` prints the counts without making anything.

**One block to paste (PowerShell, after `fillin-vocab-2` is merged).** It pulls, makes only the new vocab clips (about 176, a few minutes), pushes them, and copies everything it printed to your clipboard. Before v10.2, `push.ps1` left the `vocab/` folder out, so this push also sends the 142 vocab clips already on your PC (the app could not load them until now).
```powershell
cd A:\Citadel\citadel-sports-voice; & { git pull; powershell -ExecutionPolicy Bypass -File .\tools\run.ps1 -Only vocab; powershell -ExecutionPolicy Bypass -File .\tools\push.ps1 } *>&1 | Tee-Object -Variable out; $out | Set-Clipboard
```
Player names (`-Sleeper`) are a separate run: `powershell -ExecutionPolicy Bypass -File .\tools\run.ps1 -Sleeper`, then `push.ps1`.

## Folder layout
| Folder | What goes in it |
|---|---|
| `lines/corvus/`, `lines/bastion/` | The main booth lines, as pieces |
| `names/` | Player and team name clips, for filling the blanks in lines |
| `common/` | Shared pieces: numbers, team names, common words |
| `vocab/` | Fill-in words: penalty names, member names, deep/short, left/right/middle, run lanes, quarters, first...twelfth, clock and down words, positions, weather... (list: `tools/vocab.json`) |
| `reactions/corvus/`, `reactions/bastion/` | Short reactions to big moments |
| `interjections/corvus/`, `interjections/bastion/` | Short cut-ins when the other character is talking |
| `manifest/` | The JSON index the Voice Director reads (see `manifest/README.md`) |
| `tools/` | The generator and the PowerShell scripts Jordan runs (see `tools/README.md`) |

## Clip format
Commit **.ogg (Opus), mono, 48 kbps**. Do not commit `.wav`; the generator makes WAVs as a middle step and `.gitignore` blocks them. This keeps the repo small and the clips load fast on a phone.

## How clips are named
`<id>__<piece number>.ogg`, all lowercase, no spaces. Examples:
- `lines/corvus/c0142__01.ogg`, `lines/corvus/c0142__02.ogg`
- `names/team_kc.ogg`, `common/num_17.ogg`
- `reactions/bastion/b_react_0007.ogg`

The `id` matches the entry in the manifest, so a clip can always be traced to its text.

## Disclaimer
The voices are synthetic, made with the Kokoro text-to-speech model. They are not real people. NFL team names are trademarks of their owners and appear here only because this is a private, non-commercial fan project for a small group of friends. Nothing here is affiliated with or endorsed by the NFL or any team.

## License
Kokoro is released under Apache-2.0, which allows the audio it generates to be used, including commercially. The audio and files in this repo are shared under Apache-2.0 as well. Team names remain the property of their owners.
