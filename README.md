# citadel-sports-voice

The spoken voices for Corvus and Bastion, the two booth characters in Citadel Sports. This repo holds only the audio and the index that points to it. The app code lives in `citadel-sports`.

## The one-generation rule
Every clip is generated once, here, on Jordan's PC. The app never asks a voice engine for anything while it is open. It plays finished clips and glues them together in the browser. If a line changes, that one clip is regenerated and committed. Nothing else is touched.

## Voices
- **Corvus**: Kokoro voice `bm_fable`, speed about 0.93.
- **Bastion**: Kokoro voice `am_michael`, speed about 1.10.

Kokoro does not pause at commas, so pacing never comes from punctuation. Every line has explicit pause marks (like `[pause:250]`). The generator makes one clip per piece and the app puts the chosen gaps between them. Silence at clip edges is trimmed.

## Folder layout
| Folder | What goes in it |
|---|---|
| `lines/corvus/`, `lines/bastion/` | The main booth lines, as pieces |
| `names/` | Player and team name clips, for filling the blanks in lines |
| `common/` | Shared pieces: numbers, team names, common words |
| `reactions/corvus/`, `reactions/bastion/` | Short reactions to big moments |
| `interjections/corvus/`, `interjections/bastion/` | Short cut-ins when the other character is talking |
| `manifest/` | The JSON index the Voice Director reads (see `manifest/README.md`) |
| `tools/` | The generator script (lands here later) |

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
